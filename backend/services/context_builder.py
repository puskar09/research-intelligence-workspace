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
    """Deduplicated source entry for the API response."""
    source_id: str
    document_id: str
    page_number: int
    similarity_score: float


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
        seen_pages: set[tuple[str, int]] = set()
        sources: list[SourceReference] = []

        for i, chunk in enumerate(chunks, start=1):
            lines.append(
                f"[{i}] Source: document_id={chunk.document_id} "
                f"page={chunk.page_number} chunk={chunk.chunk_index} "
                f"(similarity={chunk.similarity_score:.4f})"
            )
            lines.append(chunk.text.strip())
            lines.append("")  # blank line separator

            # Deduplicate at page granularity for the source list.
            page_key = (chunk.document_id, chunk.page_number)
            if page_key not in seen_pages:
                seen_pages.add(page_key)
                sources.append(SourceReference(
                    source_id=chunk.source_id,
                    document_id=chunk.document_id,
                    page_number=chunk.page_number,
                    similarity_score=chunk.similarity_score,
                ))

        context_text = "\n".join(lines).rstrip()
        return context_text, sources
