import json
import logging
import re
import uuid

from sqlalchemy.orm import Session

from backend.services.context_builder import ContextBuilder
from backend.services.llm_service import BaseLLMService, LLMServiceError
from backend.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

_DISCOVERY_PROMPT = """\
You are a research discovery assistant. The user wants to explore the broad topic below.
Generate 5 to 10 distinct, useful, and specific research questions that explore different angles of this topic.
Avoid overly generic questions. Make them actionable.

If CONTEXT is provided below, make sure the questions are highly relevant to the facts and nuances found in the document context.
If web search is ALLOWED, you may include questions that require looking up current events or fresh external data.

Return ONLY a strict JSON object matching this schema:
{{
  "topic": "the topic",
  "questions": [
    {{
      "id": "q1",
      "question": "The actual question?",
      "category": "A short category label (e.g. History, Legal, Impact)"
    }}
  ]
}}

TOPIC: {topic}
WEB SEARCH ALLOWED: {web_search}

CONTEXT:
{context}
"""

def _extract_json(text: str) -> str:
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback to finding the first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text.strip()

class ResearchDiscoveryService:
    def __init__(
        self,
        llm_service: BaseLLMService,
        retrieval_service: RetrievalService | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self._llm = llm_service
        self._retrieval = retrieval_service or RetrievalService()
        self._context_builder = context_builder or ContextBuilder()
        # In-memory cache: (topic, web_search, context_text) -> dict
        self._cache: dict[tuple[str, bool, str], dict] = {}

    def discover(self, db: Session, topic: str, web_search: bool = False) -> dict:
        if not topic.strip():
            return {"topic": topic, "questions": []}

        # 1. Fetch lightweight context
        context_text = ""
        try:
            chunks = self._retrieval.search(db=db, query=topic, top_k=3)
            if chunks:
                context_text, _ = self._context_builder.build(chunks)
        except Exception as exc:
            logger.warning("Discovery retrieval failed for topic %r: %s", topic, exc)

        # 2. Check cache
        cache_key = (topic.strip().lower(), web_search, context_text)
        if cache_key in self._cache:
            logger.info("Discovery cache hit for topic=%r", topic)
            return self._cache[cache_key]

        # 3. Prompt LLM
        prompt = _DISCOVERY_PROMPT.format(
            topic=topic,
            web_search=str(web_search).lower(),
            context=context_text or "No uploaded context available."
        )

        logger.info("Discovery: generating directions for topic=%r", topic[:60])
        response_text = self._llm.generate(prompt)
        json_str = _extract_json(response_text)

        # 4. Parse and sanitize
        try:
            data = json.loads(json_str)
            if "questions" not in data or not isinstance(data["questions"], list):
                raise ValueError("Missing or invalid 'questions' array")
            
            # Ensure IDs exist
            for q in data["questions"]:
                if "id" not in q:
                    q["id"] = f"q-{uuid.uuid4().hex[:8]}"
            
            self._cache[cache_key] = data
            return data
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse discovery JSON: %s", exc)
            return {"topic": topic, "questions": []}
        except ValueError as exc:
            logger.error("Invalid discovery JSON schema: %s", exc)
            return {"topic": topic, "questions": []}
