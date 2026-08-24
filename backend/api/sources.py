"""
POST /api/sources/pdf  — ingest an uploaded PDF file
POST /api/sources/url  — ingest a web page by URL

Both endpoints return the same structured response:
  {
    "source":   Source,
    "document": DocumentSummary,   # pages omitted to keep response compact
    "chunks":   list[Chunk],
    "stats":    ChunkStats
  }
"""

import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.source import Source
from backend.services.chunker import Chunker
from backend.services.document_ingestion import DocumentIngestion, DocumentIngestionError
from backend.services.source_collector import SourceCollector, SourceCollectionError

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


class IngestionResponse(BaseModel):
    source: Source
    document: DocumentSummary
    chunks: list[Chunk]
    stats: ChunkStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(source: Source, document: Document, chunks: list[Chunk]) -> IngestionResponse:
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
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/pdf",
    response_model=IngestionResponse,
    summary="Ingest a PDF file",
    description="Upload a PDF. Returns extracted pages chunked into searchable text segments.",
)
async def ingest_pdf(file: UploadFile = File(...)) -> IngestionResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Be lenient with content_type — some clients send octet-stream.
        # We validate the extension instead.
        pass

    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a PDF (filename must end with .pdf).",
        )

    # Write upload to a temp file so pymupdf can open it by path.
    suffix = ".pdf"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            tmp.write(content)

        # Create a Source for this PDF (no URL — it's an upload).
        source = Source(
            url=None,
            title=filename,
            source_type="pdf",
        )

        try:
            document = _ingestion.ingest_pdf(tmp_path, source_id=source.id)
        except DocumentIngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        # Patch filename back to the original upload name (not the temp path).
        document.filename = filename

        chunks = _chunker.chunk_document(document)
        return _build_response(source, document, chunks)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post(
    "/url",
    response_model=IngestionResponse,
    summary="Ingest a web page by URL",
    description="Provide a URL. Returns extracted page text chunked into searchable text segments.",
)
async def ingest_url(request: URLRequest) -> IngestionResponse:
    try:
        source, document = _collector.collect(request.url)
    except SourceCollectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    chunks = _chunker.chunk_document(document)
    return _build_response(source, document, chunks)
