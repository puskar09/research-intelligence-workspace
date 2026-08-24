"""
Chunker — splits a Document into Chunks, one page at a time.

Each page is chunked independently so every Chunk carries an unambiguous
page_number. This is required for reliable source/page attribution in RAG.

Chunking strategy: sliding window with configurable size and overlap.
"""

from backend.models.chunk import Chunk
from backend.models.document import Document


class Chunker:

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        """
        Args:
            chunk_size: Maximum number of characters per chunk.
            overlap:    Number of characters to overlap between consecutive
                        chunks on the same page.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer.")
        if overlap < 0:
            raise ValueError("overlap must be zero or a positive integer.")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, document: Document) -> list[Chunk]:
        """
        Split every page of a Document into Chunks.

        Pages with no text are skipped. Short pages that fit within a single
        chunk are emitted as one chunk with chunk_index=0.

        Args:
            document: A fully populated Document (pages must be set).

        Returns:
            A flat list of Chunk objects ordered by page then chunk_index.
        """
        chunks: list[Chunk] = []

        for page in document.pages:
            text = page.text.strip()
            if not text:
                continue

            page_chunks = self._chunk_text(
                text=text,
                source_id=document.source_id,
                document_id=document.id,
                page_number=page.page_number,
            )
            chunks.extend(page_chunks)

        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _chunk_text(
        self,
        text: str,
        source_id: str,
        document_id: str,
        page_number: int,
    ) -> list[Chunk]:
        """Sliding-window chunk of a single page's text."""
        chunks: list[Chunk] = []
        start = 0
        index = 0
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            chunks.append(
                Chunk(
                    source_id=source_id,
                    document_id=document_id,
                    page_number=page_number,
                    chunk_index=index,
                    text=chunk_text,
                    char_count=len(chunk_text),
                    chunk_size=self.chunk_size,
                    overlap=self.overlap,
                )
            )

            start += step
            index += 1

        return chunks
