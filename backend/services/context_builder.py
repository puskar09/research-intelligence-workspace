"""
ContextBuilder — assembles retrieved chunks into a structured LLM prompt context.

Responsibilities:
  - Formats each chunk with its source metadata (page, chunk index, similarity).
  - Deduplicates and orders chunks by similarity score descending.
  - Produces the CONTEXT block embedded in the RAG prompt.
  - Deduplicates the source list for the API response (one entry per page).

The context format is deliberately plain-text rather than JSON so the LLM
can read it naturally without being asked to parse structured data.
"""

from dataclasses import dataclass

from backend.services.retrieval_service import RetrievalResult


@dataclass(frozen=True)
class SourceReference:
    """1:1 source entry for the API response."""
    chunk_id: str
    source_id: str
    document_id: str
    page_number: int
    similarity_score: float
    # Optional enriched fields — present when the pipeline has the data
    text: str | None = None
    source_type: str | None = None  # "pdf" | "web"
    url: str | None = None


class ContextBuilder:
    """
    Builds a numbered, page-attributed context block from retrieved chunks.

    Usage:
        builder = ContextBuilder()
        context_text, sources = builder.build(chunks)
    """

    def build(
        self,
        chunks: list[RetrievalResult],
    ) -> tuple[str, list[SourceReference]]:
        """
        Format chunks into a context string and a deduplicated source list.

        Args:
            chunks: Retrieved chunks ordered by similarity (most relevant first).

        Returns:
            (context_text, sources)
            - context_text: Multi-line string with numbered evidence blocks.
            - sources: Deduplicated list of SourceReference for the API response.
        """
        if not chunks:
            return "", []

        lines: list[str] = []
        sources: list[SourceReference] = []

        for i, chunk in enumerate(chunks, start=1):
            lines.append(
                f"[{i}] Source: document_id={chunk.document_id} "
                f"page={chunk.page_number} chunk={chunk.chunk_index} "
                f"(similarity={chunk.similarity_score:.4f})"
            )
            lines.append(chunk.text.strip())
            lines.append("")  # blank line separator

            # Determine source type and url from existing pipeline metadata.
            # Web chunks are identified by source_id == "web" (set in SourceRanker).
            # For web chunks, document_id carries the source URL.
            is_web = chunk.source_id == "web"
            source_type = "web" if is_web else "pdf"
            url = chunk.document_id if is_web else None

            # 1:1 mapping to preserve citation accuracy
            sources.append(SourceReference(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                similarity_score=chunk.similarity_score,
                text=chunk.text.strip(),
                source_type=source_type,
                url=url,
            ))

        context_text = "\n".join(lines).rstrip()
        return context_text, sources
