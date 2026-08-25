"""
POST /api/search — semantic chunk retrieval using pgvector cosine similarity.

Request:
    { "query": "...", "top_k": 5 }

Response:
    {
      "query": "...",
      "top_k": 5,
      "results_count": 5,
      "results": [
        {
          "chunk_id": "...",
          "text": "...",
          "cosine_distance": 0.123,   // lower = more similar
          "similarity_score": 0.877,  // 1 - cosine_distance, higher = more similar
          "source_id": "...",
          "document_id": "...",
          "page_number": 3,
          "chunk_index": 1
        },
        ...
      ]
    }

This endpoint does NOT generate an LLM answer — it is evidence retrieval only.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.retrieval_service import RetrievalResult, RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter()

_retrieval = RetrievalService()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language search query.")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return.")


class ChunkResult(BaseModel):
    chunk_id: str
    text: str
    cosine_distance: float
    similarity_score: float
    source_id: str
    document_id: str
    page_number: int
    chunk_index: int


class SearchResponse(BaseModel):
    query: str
    top_k: int
    results_count: int
    results: list[ChunkResult]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic chunk search",
    description=(
        "Embed the query using all-MiniLM-L6-v2 and retrieve the top_k most "
        "similar chunks from PostgreSQL using pgvector cosine distance. "
        "Returns evidence only — no LLM answer generation."
    ),
)
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    try:
        raw_results: list[RetrievalResult] = _retrieval.search(
            db=db,
            query=request.query,
            top_k=request.top_k,
        )
    except Exception as exc:
        logger.exception("Search failed for query=%r", request.query[:80])
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc

    results = [
        ChunkResult(
            chunk_id=r.chunk_id,
            text=r.text,
            cosine_distance=r.cosine_distance,
            similarity_score=r.similarity_score,
            source_id=r.source_id,
            document_id=r.document_id,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
        )
        for r in raw_results
    ]

    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        results_count=len(results),
        results=results,
    )
