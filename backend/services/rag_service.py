"""
RAGService — Retrieval-Augmented Generation pipeline.

Pipeline:
    query string
        → RetrievalService.search()      (top-k semantically similar chunks)
        → ContextBuilder.build()         (format chunks + deduplicate sources)
        → build_prompt()                 (wrap context in grounding instructions)
        → BaseLLMService.generate()      (LLM answers from context only)
        → RAGResult

Design principles:
  - RAGService owns the pipeline but not any of its components.
  - LLM, retrieval, and context-building are injected so they can be
    replaced or mocked in tests independently.
  - The LLM is instructed to answer ONLY from the provided context and to
    explicitly say so if the context is insufficient.
  - No answer is ever invented; sources are always grounded in retrieved chunks.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.services.context_builder import ContextBuilder, SourceReference
from backend.services.llm_service import BaseLLMService
from backend.services.retrieval_service import RetrievalResult, RetrievalService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are a research assistant. Answer the user's question using ONLY the evidence
provided in the CONTEXT section below.

Rules:
1. Base your answer exclusively on the CONTEXT. Do not use any external knowledge.
2. If the CONTEXT does not contain sufficient information to answer the question,
   say exactly: "The provided documents do not contain enough information to answer this question."
3. Never invent or hallucinate sources, page numbers, or facts.
4. When citing evidence, reference the chunk number in square brackets, e.g. [1] or [2].
5. Be concise and factual.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def _build_prompt(context: str, question: str) -> str:
    return _PROMPT_TEMPLATE.format(context=context, question=question)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RAGResult:
    """Complete result from a RAG query."""
    answer: str
    sources: list[SourceReference]
    chunks_retrieved: int
    context_chars: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class RAGService:
    """
    Orchestrates the RAG pipeline: retrieve → build context → generate answer.

    Args:
        retrieval_service: Provides chunk retrieval from pgvector.
        llm_service:       Provides text generation from an LLM.
        context_builder:   Formats chunks into a structured context block.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: BaseLLMService,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_service
        self._context_builder = context_builder or ContextBuilder()

    def query(
        self,
        db: Session,
        question: str,
        top_k: int = 5,
    ) -> RAGResult:
        """
        Run a full RAG query.

        Args:
            db:       Open SQLAlchemy Session.
            question: User question string.
            top_k:    Number of chunks to retrieve for context.

        Returns:
            RAGResult with the grounded answer and attributed sources.
        """
        if not question.strip():
            return RAGResult(
                answer="Please provide a question.",
                sources=[],
                chunks_retrieved=0,
                context_chars=0,
            )

        # Step 1: Retrieve relevant chunks
        chunks: list[RetrievalResult] = self._retrieval.search(
            db=db, query=question, top_k=top_k
        )
        logger.info("RAG: retrieved %d chunks for query=%r", len(chunks), question[:60])

        # Step 2: Build context block + source list
        context_text, sources = self._context_builder.build(chunks)

        # Step 3: Handle the no-evidence case gracefully
        if not context_text:
            logger.warning("RAG: no embedded chunks available for retrieval.")
            return RAGResult(
                answer=(
                    "The provided documents do not contain enough information "
                    "to answer this question."
                ),
                sources=[],
                chunks_retrieved=0,
                context_chars=0,
            )

        # Step 4: Build prompt and call LLM
        prompt = _build_prompt(context=context_text, question=question)
        logger.debug("RAG: prompt length=%d chars", len(prompt))

        answer = self._llm.generate(prompt)

        import re
        cited_indices = set(int(x) for x in re.findall(r'\[(\d+)\]', answer))
        
        if cited_indices:
            filtered_sources = [s for i, s in enumerate(sources, start=1) if i in cited_indices]
            sources = filtered_sources
        else:
            # If no citations are found (e.g. insufficient information), we can choose to return empty sources
            # or the full retrieved context. To maximize precision, we return empty sources if no citations exist.
            sources = []

        logger.info(
            "RAG: answer generated, length=%d chars, sources=%d",
            len(answer),
            len(sources),
        )

        return RAGResult(
            answer=answer,
            sources=sources,
            chunks_retrieved=len(chunks),
            context_chars=len(context_text),
        )
