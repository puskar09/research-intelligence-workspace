import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.context_builder import ContextBuilder
from backend.services.llm_service import ClaudeLLMService, LLMServiceError
from backend.services.research_discovery import ResearchDiscoveryService
from backend.services.research_service import ResearchResult, ResearchService
from backend.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter()

_research_service: ResearchService | None = None

def _get_research_service() -> ResearchService:
    global _research_service
    if _research_service is None:
        try:
            _research_service = ResearchService(
                retrieval_service=RetrievalService(),
                llm_service=ClaudeLLMService(),
                context_builder=ContextBuilder(),
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Research service unavailable: {exc}",
            ) from exc
    return _research_service

_discovery_service: ResearchDiscoveryService | None = None

def _get_discovery_service() -> ResearchDiscoveryService:
    global _discovery_service
    if _discovery_service is None:
        try:
            _discovery_service = ResearchDiscoveryService(
                llm_service=ClaudeLLMService(),
                retrieval_service=RetrievalService(),
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Discovery service unavailable: {exc}",
            ) from exc
    return _discovery_service


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ResearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Main research question.")
    web_search: bool = Field(False, description="Enable live web search for fresh sources.")


class ResearchDiscoveryRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Broad topic for discovery.")
    web_search: bool = Field(False, description="Consider web search availability.")


class DiscoveryQuestion(BaseModel):
    id: str
    question: str
    category: str


class ResearchDiscoveryResponse(BaseModel):
    topic: str
    questions: list[DiscoveryQuestion]


class FindingModel(BaseModel):
    sub_question: str
    evidence: str
    insufficient_evidence: bool


class SourceRef(BaseModel):
    chunk_id: str
    source_id: str
    document_id: str
    page_number: int
    similarity_score: float
    # Optional enriched fields — null when unavailable
    text: str | None = None
    source_type: str | None = None  # "pdf" | "web"
    url: str | None = None


class ResearchMetadata(BaseModel):
    model: str
    chunks_retrieved: int
    context_chars: int


class ResearchQueryResponse(BaseModel):
    original_query: str
    sub_questions: list[str]
    findings: list[FindingModel]
    overall_summary: str
    sources: list[SourceRef]
    metadata: ResearchMetadata


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/discover",
    response_model=ResearchDiscoveryResponse,
    summary="Research discovery — generate broad directions",
    description="Takes a broad topic and returns structured research questions."
)
def research_discover(
    request: ResearchDiscoveryRequest,
    db: Session = Depends(get_db),
) -> ResearchDiscoveryResponse:
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic must not be empty.")

    svc = _get_discovery_service()
    
    try:
        result = svc.discover(db=db, topic=request.topic, web_search=request.web_search)
    except LLMServiceError as exc:
        logger.exception("LLM call failed for discovery topic=%r", request.topic[:80])
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
    except Exception as exc:
        logger.exception("Discovery pipeline failed for topic=%r", request.topic[:80])
        raise HTTPException(
            status_code=500, detail=f"Discovery pipeline error: {exc}"
        ) from exc

    return ResearchDiscoveryResponse(**result)


@router.post(
    "/query",
    response_model=ResearchQueryResponse,
    summary="Research query — structured workflow",
    description="Breaks question into sub-questions, retrieves evidence for each, and synthesizes a structured report."
)
def research_query(
    request: ResearchQueryRequest,
    db: Session = Depends(get_db),
) -> ResearchQueryResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    svc = _get_research_service()

    try:
        result: ResearchResult = svc.query(
            db=db,
            question=request.query,
            web_search=request.web_search,
        )
    except LLMServiceError as exc:
        logger.exception("LLM call failed for research query=%r", request.query[:80])
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
    except Exception as exc:
        logger.exception("Research pipeline failed for query=%r", request.query[:80])
        raise HTTPException(
            status_code=500, detail=f"Research pipeline error: {exc}"
        ) from exc

    sources = [
        SourceRef(
            chunk_id=s.chunk_id,
            source_id=s.source_id,
            document_id=s.document_id,
            page_number=s.page_number,
            similarity_score=s.similarity_score,
            text=s.text,
            source_type=s.source_type,
            url=s.url,
        )
        for s in result.sources
    ]
    
    findings = [
        FindingModel(
            sub_question=f.sub_question,
            evidence=f.evidence,
            insufficient_evidence=f.insufficient_evidence
        )
        for f in result.findings
    ]

    return ResearchQueryResponse(
        original_query=result.original_query,
        sub_questions=result.sub_questions,
        findings=findings,
        overall_summary=result.overall_summary,
        sources=sources,
        metadata=ResearchMetadata(
            model=svc._llm.model_name,
            chunks_retrieved=result.chunks_retrieved,
            context_chars=result.context_chars,
        ),
    )
