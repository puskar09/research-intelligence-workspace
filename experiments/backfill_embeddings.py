"""
Backfill embeddings for existing chunks that have NULL embeddings.

Usage:
    python experiments/backfill_embeddings.py [--batch-size N] [--dry-run]

This script:
  - Loads the embedding model once.
  - Fetches chunks with NULL embeddings in batches.
  - Embeds each batch and updates the database.
  - Skips already-embedded chunks (WHERE embedding IS NULL).
  - Reports progress and a final summary.
  - Exits with code 1 if any batch fails, so CI/scripts can detect failure.
"""

import argparse
import logging
import sys
import time

import psycopg2

# Ensure the project root is on sys.path when run directly.
sys.path.insert(0, ".")

from backend.services.embedding_service import embed_texts, embedding_dimension, MODEL_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("backfill")

DB_PARAMS = dict(
    dbname="riw", user="riw_user", password="riw_password",
    host="localhost", port=5432,
)


def run_backfill(batch_size: int = 64, dry_run: bool = False) -> int:
    """
    Embed all chunks whose embedding IS NULL.

    Returns the number of chunks successfully embedded.
    """
    logger.info("Model: %s  dim=%d", MODEL_NAME, embedding_dimension())
    logger.info("Batch size: %d  dry_run: %s", batch_size, dry_run)

    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = False
    cur = conn.cursor()

    # Count work
    cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL")
    total_null = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_all = cur.fetchone()[0]
    logger.info(
        "Chunks: total=%d  already embedded=%d  to backfill=%d",
        total_all, total_all - total_null, total_null,
    )

    if total_null == 0:
        logger.info("Nothing to backfill.")
        cur.close()
        conn.close()
        return 0

    embedded_total = 0
    batch_num = 0
    errors = 0
    t_start = time.time()

    while True:
        cur.execute(
            "SELECT id, text FROM chunks WHERE embedding IS NULL LIMIT %s",
            (batch_size,),
        )
        rows = cur.fetchall()
        if not rows:
            break

        batch_num += 1
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]

        logger.info(
            "Batch %d: embedding %d chunks...", batch_num, len(ids)
        )

        try:
            vectors = embed_texts(texts, batch_size=batch_size)
        except Exception as exc:
            logger.error("Batch %d: embedding failed: %s", batch_num, exc)
            errors += 1
            break

        if dry_run:
            logger.info("Batch %d: [dry-run] would update %d rows.", batch_num, len(ids))
            embedded_total += len(ids)
            continue

        try:
            for chunk_id, vector in zip(ids, vectors):
                vec_str = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
                cur.execute(
                    "UPDATE chunks SET embedding = %s::vector WHERE id = %s",
                    (vec_str, chunk_id),
                )
            conn.commit()
            embedded_total += len(ids)
            elapsed = time.time() - t_start
            logger.info(
                "Batch %d: committed %d rows. Total so far: %d/%d  (%.1fs elapsed)",
                batch_num, len(ids), embedded_total, total_null, elapsed,
            )
        except Exception as exc:
            conn.rollback()
            logger.error("Batch %d: DB update failed: %s", batch_num, exc)
            errors += 1
            break

    cur.close()
    conn.close()

    elapsed = time.time() - t_start
    logger.info(
        "Backfill complete: %d/%d embedded, %d batch errors, %.1fs total.",
        embedded_total, total_null, errors, elapsed,
    )

    return embedded_total if errors == 0 else -1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill chunk embeddings.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run_backfill(batch_size=args.batch_size, dry_run=args.dry_run)
    sys.exit(0 if result >= 0 else 1)
