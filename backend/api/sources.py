"""
POST /api/sources/pdf  — ingest an uploaded PDF file and persist to PostgreSQL
POST /api/sources/url  — ingest a web page by URL and persist to PostgreSQL

Both endpoints return the same structured response:
  {
    "source":   Source,
    "document": DocumentSummary,
    "chunks":   list[Chunk],
    "stats":    ChunkStats
  }

Phase 3 change:
  After the primary persistence transaction commits, a second "post-ingestion
  embedding enrichment" step embeds all chunks and updates their embedding
  column. This is intentionally a separate transaction so that if embedding
  fails, the ingested data is already safe and can be backfilled via script.
  The API response shape is unchanged from Phase 2.
"""

import logging
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.source import Source
from backend.repositories.ingestion_repo import save_chunk_embeddings, save_ingestion
from backend.services.chunker import Chunker
from backend.services.document_ingestion import DocumentIngestion, DocumentIngestionError
from backend.services.embedding_service import embed_texts
from backend.services.source_collector import SourceCollector, SourceCollectionError

logger = logging.getLogger(__name__)

router = APIRouter()

_ingestion = DocumentIngestion()
_collector = SourceCollector()
_chunker = Chunker(chunk_size=500, overlap=50)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class URLRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def url_must_have_scheme(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class DocumentSummary(BaseModel):
    """Document metadata returned in API responses — pages omitted for brevity."""
    id: str
    source_id: str
    filename: str
    document_type: str
    total_pages: int
    total_chars: int
    extracted_at: datetime


class ChunkStats(BaseModel):
    total_chunks: int
    chunk_size: int
    overlap: int
    chunks_embedded: int


class IngestionResponse(BaseModel):
    source: Source
    document: DocumentSummary
    chunks: list[Chunk]
    stats: ChunkStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(
    source: Source,
    document: Document,
    chunks: list[Chunk],
    chunks_embedded: int,
) -> IngestionResponse:
    return IngestionResponse(
        source=source,
        document=DocumentSummary(
            id=document.id,
            source_id=document.source_id,
            filename=document.filename,
            document_type=document.document_type,
            total_pages=document.total_pages,
            total_chars=document.total_chars,
            extracted_at=document.extracted_at,
        ),
        chunks=chunks,
        stats=ChunkStats(
            total_chunks=len(chunks),
            chunk_size=_chunker.chunk_size,
            overlap=_chunker.overlap,
            chunks_embedded=chunks_embedded,
        ),
    )


def _persist_ingestion(
    db: Session,
    source: Source,
    document: Document,
    chunks: list[Chunk],
) -> None:
    """Transaction A — persist source/document/pages/chunks (no embeddings)."""
    try:
        save_ingestion(db, source, document, chunks)
        db.commit()
        logger.info("Persisted source=%s to database.", source.id)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("DB error persisting source=%s", source.id)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion succeeded but database persistence failed: {exc}",
        ) from exc


def _enrich_embeddings(
    db: Session,
    chunks: list[Chunk],
) -> int:
    """
    Transaction B — post-ingestion embedding enrichment.

    Embeds all chunk texts and stores them. If this step fails, the ingestion
    data from transaction A is already safe and can be backfilled separately.

    Returns the number of chunks successfully embedded.
    """
    if not chunks:
        return 0
    try:
        texts = [c.text for c in chunks]
        vectors = embed_texts(texts)
        chunk_id_to_embedding = {c.id: v for c, v in zip(chunks, vectors)}
        updated = save_chunk_embeddings(db, chunk_id_to_embedding)
        db.commit()
        logger.info("Embedded %d chunks for ingestion.", updated)
        return updated
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        # Log but do NOT raise — data is already persisted; backfill can fix this.
        logger.error(
            "Post-ingestion embedding enrichment failed (data is safe, run backfill): %s",
            exc,
        )
        return 0


def _enrich_embeddings_bg(chunks: list[Chunk]) -> None:
    from backend.db.database import SessionLocal
    db = SessionLocal()
    try:
        _enrich_embeddings(db, chunks)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/pdf",
    response_model=IngestionResponse,
    summary="Ingest a PDF file",
    description=(
        "Upload a PDF. Extracts text page-by-page, chunks each page independently, "
        "persists to PostgreSQL (transaction A), then embeds chunks (transaction B). "
        "If embedding fails, data is still persisted and can be backfilled."
    ),
)
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> IngestionResponse:
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a PDF (filename must end with .pdf).",
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            tmp.write(content)

        source = Source(url=None, title=filename, source_type="pdf")

        try:
            document = _ingestion.ingest_pdf(tmp_path, source_id=source.id)
        except DocumentIngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        document.filename = filename
        chunks = _chunker.chunk_document(document)

        # Transaction A — persist ingestion data
        _persist_ingestion(db, source, document, chunks)
        # Transaction B — post-ingestion embedding enrichment
        background_tasks.add_task(_enrich_embeddings_bg, chunks)
        embedded = 0

        return _build_response(source, document, chunks, embedded)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post(
    "/url",
    response_model=IngestionResponse,
    summary="Ingest a web page by URL",
    description=(
        "Fetch a URL, extract text, chunk it, persist to PostgreSQL (transaction A), "
        "then embed chunks (transaction B)."
    ),
)
async def ingest_url(
    request: URLRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> IngestionResponse:
    try:
        source, document = _collector.collect(request.url)
    except SourceCollectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    chunks = _chunker.chunk_document(document)

    # Transaction A — persist ingestion data
    _persist_ingestion(db, source, document, chunks)
    # Transaction B — post-ingestion embedding enrichment
    background_tasks.add_task(_enrich_embeddings_bg, chunks)
    embedded = 0

    return _build_response(source, document, chunks, embedded)


@router.delete(
    "/{source_id}",
    status_code=204,
    summary="Delete a source and all indexed data",
    description="Permanently removes a source and its associated documents, pages, chunks, and embeddings.",
)
async def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
) -> None:
    from backend.db.orm_models import SourceORM
    from sqlalchemy.exc import SQLAlchemyError
    
    try:
        source = db.query(SourceORM).filter(SourceORM.id == source_id).first()
        if not source:
            raise HTTPException(
                status_code=404,
                detail=f"Source with id '{source_id}' not found.",
            )
        db.delete(source)
        db.commit()
        logger.info("Deleted source=%s and all associated data.", source_id)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("DB error deleting source=%s", source_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete source due to a database error.",
        ) from exc
