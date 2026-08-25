"""
Phase 3 verification script — Embeddings + Semantic Retrieval.

Run AFTER:
  1. docker compose up -d
  2. uvicorn backend.main:app --host 127.0.0.1 --port 8001

Usage:
  python experiments/verify_phase3.py

Checks:
  1.  Embedding model loads (all-MiniLM-L6-v2)
  2.  Single string embeds to a 384-float vector
  3.  Embedding dimension = 384
  4.  DB schema: chunks.embedding column exists with dim=384
  5.  Backfill: NULL embeddings are filled by backfill_embeddings.py
  6.  Zero NULL embeddings remain after backfill
  7.  New ingestion via POST /api/sources/pdf receives embeddings
  8.  POST /api/search returns 200 with results
  9.  top_k=3 returns exactly 3 results
  10. Result metadata fields all present (chunk_id, source_id, doc_id, page, chunk_index)
  11. cosine_distance and similarity_score both present; sim = 1 - dist
  12. Multiple semantic queries return plausibly relevant chunks
"""

import sys
import os
import json
import time

import requests
import psycopg2
from pathlib import Path

BASE_URL = "http://127.0.0.1:8001"
DB_PARAMS = dict(dbname="riw", user="riw_user", password="riw_password",
                 host="localhost", port=5432)
PDF_PATH = Path("data/raw/test.pdf")

PASS = "[PASS]"
FAIL = "[FAIL]"

_failures = []


def section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check(label, condition, detail=""):
    suffix = f" -- {detail}" if detail else ""
    if condition:
        print(f"  {PASS}  {label}{suffix}")
    else:
        print(f"  {FAIL}  {label}{suffix}")
        _failures.append(label)


def require(label, condition, detail=""):
    """Like check() but aborts if False."""
    check(label, condition, detail)
    if not condition:
        print(f"\n  FATAL: '{label}' failed — cannot continue.\n")
        _report_and_exit()


def _report_and_exit():
    print("\n" + "=" * 60)
    if _failures:
        print(f"  FAILED: {len(_failures)} check(s) did not pass:")
        for f in _failures:
            print(f"    - {f}")
    else:
        print("  All checks passed [OK]")
    print("=" * 60 + "\n")
    sys.exit(1 if _failures else 0)


# ── 1. Embedding model loads ─────────────────────────────────────────────────
section("1. Embedding model and dimension")

# Import after sys.path adjustment (script runs from project root)
sys.path.insert(0, ".")
from backend.services.embedding_service import (
    embed_text, embed_texts, embedding_dimension, MODEL_NAME
)

print(f"  Model: {MODEL_NAME}")
dim = embedding_dimension()
print(f"  Dimension: {dim}")
check("Model loaded", dim > 0, f"dim={dim}")
check("Dimension is 384", dim == 384, f"got {dim}")

# ── 2. Single embed ─────────────────────────────────────────────────────────
section("2. Single text embedding")
vec = embed_text("test embedding")
check("embed_text returns list", isinstance(vec, list))
check("embed_text length = 384", len(vec) == 384, f"got {len(vec)}")
check("embed_text values are float", all(isinstance(v, float) for v in vec[:5]))

# ── 3. Batch embed ──────────────────────────────────────────────────────────
section("3. Batch embedding")
texts = ["first chunk", "second chunk", "third chunk"]
vecs = embed_texts(texts)
check("embed_texts returns list of 3", len(vecs) == 3)
check("each vector is 384-dim", all(len(v) == 384 for v in vecs))

# ── 4. DB schema ─────────────────────────────────────────────────────────────
section("4. Database schema — chunks.embedding column")
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor()

cur.execute("""
    SELECT udt_name
    FROM information_schema.columns
    WHERE table_name = 'chunks' AND column_name = 'embedding'
""")
row = cur.fetchone()
require("chunks.embedding column exists", row is not None)
print(f"  Column type: {row[0]}")
check("Column type is vector", "vector" in str(row[0]).lower())

# Check registered vector dimension via pg_attribute
cur.execute("""
    SELECT atttypmod
    FROM pg_attribute
    WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'
""")
atttypmod = cur.fetchone()[0]
# pgvector stores the dimension directly as atttypmod (not dim+1).
col_dim = atttypmod if atttypmod > 0 else -1
print(f"  Vector dimension from schema: {col_dim}")
check("Schema dimension = 384", col_dim == 384, f"got {col_dim}")

# ── 5. Current NULL count ────────────────────────────────────────────────────
section("5. Embedding coverage before backfill")
cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL")
null_before = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM chunks")
total_chunks = cur.fetchone()[0]
print(f"  Total chunks: {total_chunks}")
print(f"  NULL embeddings (before backfill): {null_before}")
print(f"  Already embedded: {total_chunks - null_before}")

# ── 6. Backfill ───────────────────────────────────────────────────────────────
if null_before > 0:
    section(f"6. Backfilling {null_before} chunks")
    import subprocess
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "experiments/backfill_embeddings.py", "--batch-size", "64"],
        capture_output=True, text=True
    )
    elapsed = time.time() - t0
    print(result.stdout.strip())
    if result.stderr.strip():
        print("STDERR:", result.stderr.strip()[:500])
    require("Backfill script exited 0", result.returncode == 0,
            f"exit code={result.returncode}")
    print(f"  Backfill completed in {elapsed:.1f}s")
else:
    section("6. Backfill (skipped — all chunks already embedded)")
    print("  Nothing to backfill.")

# ── 7. Zero NULLs after backfill ─────────────────────────────────────────────
section("7. NULL embedding count after backfill")
cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL")
null_after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL")
embedded_after = cur.fetchone()[0]
print(f"  Embedded: {embedded_after}/{total_chunks}")
print(f"  NULLs remaining: {null_after}")
check("Zero NULL embeddings after backfill", null_after == 0, f"still {null_after} NULL")

cur.close()
conn.close()

# ── 8. /health check ────────────────────────────────────────────────────────
section("8. API health check")
r = requests.get(f"{BASE_URL}/health", timeout=5)
require("/health returns 200", r.status_code == 200, r.text[:100])
check("/health body correct", r.json() == {"status": "ok"})

# ── 9. New ingestion receives embeddings ──────────────────────────────────────
section("9. New ingestion via POST /api/sources/url")
r = requests.post(f"{BASE_URL}/api/sources/url",
                  json={"url": "https://example.com"}, timeout=30)
require("POST /api/sources/url -> 200", r.status_code == 200, r.text[:200])
ingest_data = r.json()
url_source_id = ingest_data["source"]["id"]
chunks_embedded_in_response = ingest_data["stats"].get("chunks_embedded", -1)
total_chunks_in_response = ingest_data["stats"]["total_chunks"]
print(f"  source_id: {url_source_id}")
print(f"  chunks: {total_chunks_in_response}  embedded: {chunks_embedded_in_response}")
check("chunks_embedded field present", chunks_embedded_in_response >= 0)
check("New chunks got embeddings", chunks_embedded_in_response == total_chunks_in_response,
      f"{chunks_embedded_in_response}/{total_chunks_in_response}")

# Verify in DB
conn2 = psycopg2.connect(**DB_PARAMS)
cur2 = conn2.cursor()
cur2.execute("SELECT COUNT(*) FROM chunks WHERE source_id = %s AND embedding IS NULL",
             (url_source_id,))
null_new = cur2.fetchone()[0]
check("New source has zero NULL embeddings in DB", null_new == 0, f"{null_new} NULLs")
cur2.close()
conn2.close()

# ── 10. POST /api/search basic ───────────────────────────────────────────────
section("10. POST /api/search — basic functionality")
r = requests.post(f"{BASE_URL}/api/search",
                  json={"query": "foreign contribution regulation", "top_k": 5},
                  timeout=15)
require("POST /api/search -> 200", r.status_code == 200, r.text[:200])
search_data = r.json()
check("results_count in response", "results_count" in search_data)
check("results list in response", "results" in search_data)
check("results_count > 0", search_data["results_count"] > 0,
      f"got {search_data['results_count']}")

# ── 11. top_k=3 returns exactly 3 ───────────────────────────────────────────
section("11. top_k=3 returns exactly 3 results")
r3 = requests.post(f"{BASE_URL}/api/search",
                   json={"query": "penalty offence", "top_k": 3},
                   timeout=15)
require("top_k=3 search -> 200", r3.status_code == 200)
d3 = r3.json()
check("results_count = 3", d3["results_count"] == 3, f"got {d3['results_count']}")
check("results list length = 3", len(d3["results"]) == 3)

# ── 12. Metadata correctness ─────────────────────────────────────────────────
section("12. Result metadata fields")
result = search_data["results"][0]
required_fields = ["chunk_id", "text", "cosine_distance", "similarity_score",
                   "source_id", "document_id", "page_number", "chunk_index"]
for field in required_fields:
    check(f"Field '{field}' present", field in result)

check("page_number >= 1", result["page_number"] >= 1, f"got {result['page_number']}")
check("chunk_index >= 0", result["chunk_index"] >= 0, f"got {result['chunk_index']}")
check("cosine_distance >= 0", result["cosine_distance"] >= 0)
check("similarity_score = 1 - cosine_distance",
      abs(result["similarity_score"] - (1.0 - result["cosine_distance"])) < 1e-4,
      f"sim={result['similarity_score']}  dist={result['cosine_distance']}")
check("text is non-empty string", isinstance(result["text"], str) and len(result["text"]) > 0)

# ── 13. Results ordered by distance ASC ──────────────────────────────────────
section("13. Results ordered by cosine_distance ascending")
dists = [r["cosine_distance"] for r in search_data["results"]]
check("cosine_distance is non-decreasing", dists == sorted(dists),
      f"dists={dists}")

# ── 14. Semantic retrieval quality ───────────────────────────────────────────
section("14. Semantic retrieval quality (manual spot-checks on test.pdf)")

QUERIES = [
    {
        "query": "registration of foreign contribution",
        "expected_keywords": ["registration", "certificate", "contribution"],
        "description": "FCRA registration requirements",
    },
    {
        "query": "penalty for violation of foreign contribution rules",
        "expected_keywords": ["penalty", "offence", "fine", "punish"],
        "description": "penalties for FCRA violations",
    },
    {
        "query": "bank account for receiving foreign contribution",
        "expected_keywords": ["bank", "account", "schedule"],
        "description": "banking requirements for foreign funds",
    },
]

all_semantic_ok = True
for q in QUERIES:
    r = requests.post(f"{BASE_URL}/api/search",
                      json={"query": q["query"], "top_k": 5},
                      timeout=15)
    if r.status_code != 200:
        check(f"Query '{q['description']}' -> 200", False, f"status={r.status_code}")
        all_semantic_ok = False
        continue

    data = r.json()
    results = data["results"]
    if not results:
        check(f"Query '{q['description']}' has results", False, "empty results")
        all_semantic_ok = False
        continue

    # Check if any keyword appears in the top 5 results
    combined_text = " ".join(r["text"].lower() for r in results)
    found_any = any(kw in combined_text for kw in q["expected_keywords"])
    check(
        f"Query '{q['description']}' — relevant keywords in top-5",
        found_any,
        f"keywords={q['expected_keywords']}  top_sim={results[0]['similarity_score']:.4f}"
    )
    # Print top result for manual inspection
    top = results[0]
    preview = top["text"][:120].replace("\n", " ")
    print(f"    Top result (p{top['page_number']} chunk{top['chunk_index']},"
          f" sim={top['similarity_score']:.4f}): {preview}...")

# ── Summary ───────────────────────────────────────────────────────────────────
_report_and_exit()
