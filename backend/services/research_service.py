import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.services.context_builder import ContextBuilder, SourceReference
from backend.services.llm_service import BaseLLMService, LLMServiceError
from backend.services.retrieval_service import RetrievalResult, RetrievalService
from backend.services.source_ranker import SourceRanker
from backend.services.web_research_service import WebResearchService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SUB_QUESTIONS_PROMPT = """\
You are a research assistant. Break the following research question into 3-5 focused sub-questions.
The sub-questions should help cover different aspects of the main question.

Return ONLY a JSON array of strings. Do not include any other text or markdown formatting.

Question: {question}

Example Output:
[
  "Sub-question 1?",
  "Sub-question 2?",
  "Sub-question 3?"
]
"""

_SYNTHESIS_PROMPT = """\
You are a research assistant. Answer the user's main research question and the specific sub-questions using ONLY the evidence provided in the CONTEXT section below.

Rules:
1. Base your answer exclusively on the CONTEXT. Do not use any external knowledge.
2. If the CONTEXT does not contain sufficient information to answer a sub-question, set "insufficient_evidence" to true and explain that the evidence is missing.
3. Never invent or hallucinate sources, page numbers, or facts.
4. When citing evidence in your findings, reference the chunk number in square brackets, e.g. [1] or [2].
5. Be concise and factual.

Return ONLY a JSON object with the following schema (do not include markdown block formatting):
{{
  "findings": [
    {{
      "sub_question": "string (the exact sub-question)",
      "evidence": "string (the grounded answer with citations)",
      "insufficient_evidence": boolean
    }}
  ],
  "overall_summary": "string (a synthesized overall answer to the main question based on the findings, or stating if the context was insufficient overall)"
}}

CONTEXT:
{context}

MAIN QUESTION:
{question}

SUB-QUESTIONS:
{sub_questions}
"""

def _extract_json(text: str) -> str:
    """Extract JSON from potential markdown blocks or surrounding prose."""
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: locate the first { and last } to handle prose-wrapped JSON
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text.strip()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    sub_question: str
    evidence: str
    insufficient_evidence: bool

@dataclass
class ResearchResult:
    original_query: str
    sub_questions: list[str]
    findings: list[Finding]
    overall_summary: str
    sources: list[SourceReference]
    chunks_retrieved: int
    context_chars: int

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ResearchService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_service: BaseLLMService,
        context_builder: ContextBuilder | None = None,
        web_research_service: WebResearchService | None = None,
        source_ranker: SourceRanker | None = None,
    ) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_service
        self._context_builder = context_builder or ContextBuilder()
        self._web_research = web_research_service or WebResearchService()
        self._source_ranker = source_ranker or SourceRanker()

    def _generate_sub_questions(self, question: str) -> list[str]:
        prompt = _SUB_QUESTIONS_PROMPT.format(question=question)
        response_text = self._llm.generate(prompt)
        json_str = _extract_json(response_text)
        try:
            sub_questions = json.loads(json_str)
            if not isinstance(sub_questions, list):
                raise ValueError("Expected a JSON array")
            return [str(q) for q in sub_questions][:5]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse sub-questions: %s. Response: %s", exc, response_text)
            # Fallback if generation fails
            return [question]

    def _generate_synthesis(self, context: str, question: str, sub_questions: list[str]) -> dict:
        sq_str = json.dumps(sub_questions, indent=2)
        prompt = _SYNTHESIS_PROMPT.format(context=context, question=question, sub_questions=sq_str)
        response_text = self._llm.generate(prompt)
        json_str = _extract_json(response_text)
        try:
            data = json.loads(json_str)
            logger.info("Research: Synthesis succeeded on first attempt.")
            return data
        except json.JSONDecodeError as exc:
            logger.warning("Research: Synthesis JSON parsing failed (possibly truncated). Attempting ONE repair retry. Error: %s", exc)
            repair_prompt = (
                f"{prompt}\n\n"
                f"--- ERROR IN PREVIOUS ATTEMPT ---\n"
                f"Your previous response failed to parse as valid JSON. It may have been truncated or malformed.\n"
                f"Error details: {exc}\n\n"
                f"Please try again. Provide ONLY the completely fixed, valid JSON object following the exact schema required. "
                f"Ensure your output is complete and not truncated. Do not include markdown blocks or any other text."
            )
            retry_text = self._llm.generate(repair_prompt)
            retry_json_str = _extract_json(retry_text)
            try:
                data = json.loads(retry_json_str)
                logger.info("Research: Synthesis repair retry succeeded.")
                return data
            except json.JSONDecodeError as retry_exc:
                logger.error("Research: Synthesis repair retry also failed: %s. Response: %s", retry_exc, retry_text)
                return {
                    "findings": [],
                    "overall_summary": "Failed to generate structured synthesis due to model output error."
                }

    def query(
        self,
        db: Session,
        question: str,
        web_search: bool = False,
    ) -> ResearchResult:
        if not question.strip():
            return ResearchResult(
                original_query=question,
                sub_questions=[],
                findings=[],
                overall_summary="Please provide a question.",
                sources=[],
                chunks_retrieved=0,
                context_chars=0,
            )

        logger.info("Research: generating sub-questions for %r", question[:60])
        sub_questions = self._generate_sub_questions(question)
        if not sub_questions:
            sub_questions = [question]

        logger.info("Research: generated %d sub-questions", len(sub_questions))

        all_chunks: dict[str, RetrievalResult] = {}
        
        for sq in sub_questions:
            local_chunks = self._retrieval.search(db=db, query=sq, top_k=3)
            
            web_chunks = []
            if web_search:
                web_chunks = self._web_research.get_web_chunks(query=sq, max_urls=2)
                
            ranked = self._source_ranker.rank(
                query=sq,
                local_results=local_chunks,
                web_chunks=web_chunks,
                top_k=3
            )
            
            for c in ranked:
                all_chunks[c.chunk_id] = c
                
        unique_chunks = list(all_chunks.values())
        logger.info("Research: retrieved %d unique chunks across %d queries", len(unique_chunks), len(sub_questions))

        context_text, sources = self._context_builder.build(unique_chunks)

        if not context_text:
            return ResearchResult(
                original_query=question,
                sub_questions=sub_questions,
                findings=[Finding(sq, "Insufficient evidence", True) for sq in sub_questions],
                overall_summary="The provided documents do not contain enough information to answer this question.",
                sources=[],
                chunks_retrieved=0,
                context_chars=0,
            )

        synthesis_data = self._generate_synthesis(context_text, question, sub_questions)

        findings = []
        for f_data in synthesis_data.get("findings", []):
            findings.append(Finding(
                sub_question=f_data.get("sub_question", ""),
                evidence=f_data.get("evidence", ""),
                insufficient_evidence=f_data.get("insufficient_evidence", False)
            ))

        return ResearchResult(
            original_query=question,
            sub_questions=sub_questions,
            findings=findings,
            overall_summary=synthesis_data.get("overall_summary", ""),
            sources=sources,
            chunks_retrieved=len(unique_chunks),
            context_chars=len(context_text),
        )
