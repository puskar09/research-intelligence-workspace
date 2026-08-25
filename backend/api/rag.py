"""
POST /api/rag/query — Retrieval-Augmented Generation endpoint.

Request:
    { "query": "...", "top_k": 5 }

Response:
    {
      "answer": "...",
      "sources": [
        {
          "source_id": "...",
          "document_id": "...",
          "page_number": 1,
          "similarity_score": 0.82
        }
      ],
      "metadata": {
        "model": "gemini-3.6-flash",
        "chunks_retrieved": 5,
        "context_chars": 2341,
        "top_k": 5
      }
    }

The answer is grounded exclusively in the retrieved chunks.
If the context is insufficient, the answer states so explicitly.
Sources are deduplicated at page granularity.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.context_builder import ContextBuilder
from backend.services.llm_service import GeminiLLMService, LLMServiceError
from backend.services.rag_service import RAGResult, RAGService
from backend.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level singletons — instantiated once at import time.
# GeminiLLMService raises LLMServiceError at init if GOOGLE_API_KEY is missing,
# but we defer that to request time by using a lazy factory pattern.
_rag_service: RAGService | None = None


def _get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        try:
            _rag_service = RAGService(
                retrieval_service=RetrievalService(),
                llm_service=GeminiLLMService(),
                context_builder=ContextBuilder(),
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"RAG service unavailable: {exc}",
            ) from exc
    return _rag_service


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language question.")
    top_k: int = Field(default=5, ge=1, le=20, description="Chunks to retrieve.")


class SourceRef(BaseModel):
    source_id: str
    document_id: str
    page_number: int
    similarity_score: float


class RAGMetadata(BaseModel):
    model: str
    chunks_retrieved: int
    context_chars: int
    top_k: int


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    metadata: RAGMetadata


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/query",
    response_model=RAGQueryResponse,
    summary="RAG query — grounded answer from retrieved chunks",
    description=(
        "Retrieve the top_k most relevant chunks from PostgreSQL, assemble "
        "them as context, and ask Gemini to answer using only that context. "
        "If the context is insufficient, the answer says so explicitly."
    ),
)
def rag_query(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    svc = _get_rag_service()

    try:
        result: RAGResult = svc.query(
            db=db,
            question=request.query,
            top_k=request.top_k,
        )
    except LLMServiceError as exc:
        logger.exception("LLM call failed for query=%r", request.query[:80])
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
    except Exception as exc:
        logger.exception("RAG pipeline failed for query=%r", request.query[:80])
        raise HTTPException(
            status_code=500, detail=f"RAG pipeline error: {exc}"
        ) from exc

    sources = [
        SourceRef(
            source_id=s.source_id,
            document_id=s.document_id,
            page_number=s.page_number,
            similarity_score=s.similarity_score,
        )
        for s in result.sources
    ]

    return RAGQueryResponse(
        answer=result.answer,
        sources=sources,
        metadata=RAGMetadata(
            model=svc._llm.model_name,
            chunks_retrieved=result.chunks_retrieved,
            context_chars=result.context_chars,
            top_k=request.top_k,
        ),
    )
