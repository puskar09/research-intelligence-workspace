"""
SQLAlchemy ORM table definitions.

These map 1-to-1 with the database tables:

    sources
      └─ documents
           ├─ pages
           └─ chunks

Column names match the domain model field names exactly so the
repository layer can copy attributes without renaming anything.

Phase 3 change: ChunkORM now has an `embedding` column of type
pgvector Vector(384), matching all-MiniLM-L6-v2.  The column is
nullable so Phase 2 rows are unaffected until backfilled.
"""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Dimension must match EmbeddingService.MODEL_NAME (all-MiniLM-L6-v2 = 384).
EMBEDDING_DIM: int = 384


class Base(DeclarativeBase):
    pass


class SourceORM(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'pdf' | 'url'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    documents: Mapped[list["DocumentORM"]] = relationship(
        "DocumentORM", back_populates="source", cascade="all, delete-orphan"
    )


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    source: Mapped["SourceORM"] = relationship("SourceORM", back_populates="documents")
    pages: Mapped[list["PageORM"]] = relationship(
        "PageORM", back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["ChunkORM"]] = relationship(
        "ChunkORM", back_populates="document", cascade="all, delete-orphan"
    )


class PageORM(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped["DocumentORM"] = relationship("DocumentORM", back_populates="pages")


class ChunkORM(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    overlap: Mapped[int] = mapped_column(Integer, nullable=False)
    # Phase 3: nullable so existing rows are safe until backfilled.
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    document: Mapped["DocumentORM"] = relationship("DocumentORM", back_populates="chunks")
