"""
RetrievalService — semantic chunk retrieval using pgvector cosine similarity.

Query flow:
    query string
        → EmbeddingService.embed_text()     (384-dim cosine-normalised vector)
        → pgvector <=> cosine distance search on chunks.embedding
        → top_k rows ordered by cosine_distance ASC
        → list[RetrievalResult]

Distance metric: cosine (<=>)
  - All-MiniLM-L6-v2 is trained with cosine similarity objectives.
  - Vectors are normalised at embed time so cosine_distance = 1 - dot_product.
  - Lower cosine_distance = more similar.
  - similarity_score = 1 - cosine_distance, higher = more similar (0..1 range).

Both scores are surfaced in RetrievalResult for ease of debugging.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.embedding_service import embed_text

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieved chunk with its metadata and relevance scores."""

    chunk_id: str
    text: str
    cosine_distance: float   # pgvector <=> output; lower = more similar
    similarity_score: float  # 1 - cosine_distance; higher = more similar (0..1)
    source_id: str
    document_id: str
    page_number: int
    chunk_index: int


class RetrievalService:

    def search(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
        query_vector: list[float] | None = None,
    ) -> list[RetrievalResult]:
        """
        Embed the query and return the top_k most similar chunks.

        Only chunks that have a non-NULL embedding are considered.
        If no chunks are embedded yet, returns an empty list.

        Args:
            db:     Open SQLAlchemy Session.
            query:  Natural-language query string.
            top_k:  Number of results to return.

        Returns:
            List of RetrievalResult ordered by cosine_distance ascending
            (most relevant first).
        """
        if not query.strip():
            return []
        
        if query_vector is None:
            query_vector = embed_text(query)

        # pgvector cosine distance operator: <=>
        # Cast the Python list to a pgvector literal so psycopg2 sends it correctly.
        sql = text("""
            SELECT
                id,
                text,
                (embedding <=> CAST(:qvec AS vector)) AS cosine_distance,
                source_id,
                document_id,
                page_number,
                chunk_index
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY cosine_distance ASC
            LIMIT :top_k
        """)

        # pgvector expects a string like '[0.1, 0.2, ...]'
        qvec_str = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"

        rows = db.execute(sql, {"qvec": qvec_str, "top_k": top_k}).fetchall()

        results: list[RetrievalResult] = []
        for row in rows:
            dist = float(row.cosine_distance)
            results.append(
                RetrievalResult(
                    chunk_id=row.id,
                    text=row.text,
                    cosine_distance=round(dist, 6),
                    similarity_score=round(1.0 - dist, 6),
                    source_id=row.source_id,
                    document_id=row.document_id,
                    page_number=row.page_number,
                    chunk_index=row.chunk_index,
                )
            )

        logger.info(
            "search: query=%r top_k=%d results=%d",
            query[:60],
            top_k,
            len(results),
        )
        return results
