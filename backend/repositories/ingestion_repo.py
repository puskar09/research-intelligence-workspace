"""
IngestionRepository — persists a complete ingestion result atomically.

Public functions:
  save_ingestion(db, source, document, chunks)
      Writes Source, Document, Pages, and Chunks in one session.
      Caller owns commit/rollback.

  save_chunk_embeddings(db, chunk_id_to_embedding)
      Phase 3: Updates the embedding column for a batch of chunks.
      Called separately from save_ingestion (post-ingestion enrichment).
      Caller owns commit/rollback.

Design note:
  Ingestion and embedding are separate transactions by design.
  If embedding fails, data is already persisted and can be backfilled.
"""

import logging

from sqlalchemy.orm import Session

from backend.db.orm_models import ChunkORM, DocumentORM, PageORM, SourceORM
from backend.models.chunk import Chunk
from backend.models.document import Document
from backend.models.source import Source

logger = logging.getLogger(__name__)


def save_ingestion(
    db: Session,
    source: Source,
    document: Document,
    chunks: list[Chunk],
) -> None:
    """
    Persist a Source, its Document, all Pages, and all Chunks.

    The caller owns the session and is responsible for calling db.commit()
    or db.rollback(). This keeps the transaction boundary at the API layer.

    Args:
        db:       Open SQLAlchemy Session (from get_db dependency).
        source:   Domain Source model.
        document: Domain Document model (must include populated .pages list).
        chunks:   List of domain Chunk models.
    """
    db.add(SourceORM(
        id=source.id,
        url=source.url,
        title=source.title,
        source_type=source.source_type,
        created_at=source.created_at,
    ))

    db.add(DocumentORM(
        id=document.id,
        source_id=document.source_id,
        filename=document.filename,
        document_type=document.document_type,
        total_pages=document.total_pages,
        total_chars=document.total_chars,
        extracted_at=document.extracted_at,
    ))

    for page in document.pages:
        db.add(PageORM(
            document_id=document.id,
            page_number=page.page_number,
            text=page.text,
            char_count=page.char_count,
        ))

    for chunk in chunks:
        db.add(ChunkORM(
            id=chunk.id,
            source_id=chunk.source_id,
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            char_count=chunk.char_count,
            chunk_size=chunk.chunk_size,
            overlap=chunk.overlap,
            # embedding is NULL at write time; enriched separately.
        ))

    logger.info(
        "Staged ingestion for source=%s document=%s pages=%d chunks=%d",
        source.id,
        document.id,
        len(document.pages),
        len(chunks),
    )


def save_chunk_embeddings(
    db: Session,
    chunk_id_to_embedding: dict[str, list[float]],
) -> int:
    """
    Update the embedding column for a batch of chunks.

    This is the post-ingestion enrichment step — called after save_ingestion
    has already committed. Caller owns commit/rollback.

    Args:
        db:                     Open SQLAlchemy Session.
        chunk_id_to_embedding:  Mapping of chunk UUID → embedding vector.

    Returns:
        Number of rows successfully updated.
    """
    updated = 0
    for chunk_id, vector in chunk_id_to_embedding.items():
        row = db.get(ChunkORM, chunk_id)
        if row is not None:
            row.embedding = vector
            updated += 1
        else:
            logger.warning("save_chunk_embeddings: chunk %s not found in DB", chunk_id)

    logger.info("Staged %d chunk embedding updates.", updated)
    return updated
