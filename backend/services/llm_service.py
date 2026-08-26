"""
LLM service abstraction — provider-swappable LLM interface.

Design:
  - BaseLLMService defines the contract: generate(prompt) -> str
  - GeminiLLMService implements it using the google-genai SDK
  - The RAGService depends only on BaseLLMService, so the provider
    can be replaced by swapping the concrete class (e.g. OpenAILLMService)
    without touching any RAG logic.

Configuration:
  - GOOGLE_API_KEY must be set in the environment (loaded from .env).
  - LLM_MODEL env var overrides the default model name.

Usage:
    from backend.services.llm_service import GeminiLLMService
    llm = GeminiLLMService()
    answer = llm.generate("Your prompt here")
"""

import logging
import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Default stable Flash model; override via LLM_MODEL env var.
_DEFAULT_MODEL = "gemini-3.6-flash"


class BaseLLMService(ABC):
    """
    Abstract base for all LLM providers.

    Concrete implementations must implement generate().
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Send a prompt to the LLM and return the text response.

        Args:
            prompt: Full prompt string including any context.

        Returns:
            Model response as a plain string.

        Raises:
            LLMServiceError: On API or configuration failure.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable identifier of the model being used."""
        ...


class LLMServiceError(Exception):
    """Raised when the LLM provider returns an error or is misconfigured."""


class GeminiLLMService(BaseLLMService):
    """
    LLM service backed by Google Gemini via the google-genai SDK.

    Reads GOOGLE_API_KEY from the environment.
    Model defaults to gemini-3.6-flash; override with LLM_MODEL env var.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            raise LLMServiceError(
                "GOOGLE_API_KEY is not set. "
                "Add it to your .env file: GOOGLE_API_KEY=your-key-here"
            )
        self._model = os.environ.get("LLM_MODEL", _DEFAULT_MODEL)

        # Import here so the module can be imported even if google-genai
        # is not installed yet (e.g. during IDE type-checking).
        try:
            from google import genai as _genai
            self._client = _genai.Client(api_key=api_key)
        except ImportError as exc:
            raise LLMServiceError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        logger.info("GeminiLLMService ready: model=%s", self._model)

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Gemini and return the text response.

        Raises:
            LLMServiceError: On API error or empty response.
        """
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            text = response.text
            if not text:
                raise LLMServiceError("Gemini returned an empty response.")
            logger.debug("LLM response length: %d chars", len(text))
            return text.strip()
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.exception("Gemini API call failed")
            raise LLMServiceError(f"Gemini API error: {exc}") from exc


class ClaudeLLMService(BaseLLMService):
    """
    LLM service backed by Anthropic Claude via the anthropic SDK.

    Reads ANTHROPIC_API_KEY and CLAUDE_MODEL from the environment.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise LLMServiceError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file: ANTHROPIC_API_KEY=your-key-here"
            )
            
        self._model = os.environ.get("CLAUDE_MODEL", "")
        if not self._model:
            raise LLMServiceError(
                "CLAUDE_MODEL is not set. "
                "Add it to your .env file (e.g., CLAUDE_MODEL=claude-3-5-sonnet-20241022)"
            )

        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise LLMServiceError(
                "anthropic is not installed. Run: pip install anthropic"
            ) from exc

        logger.info("ClaudeLLMService ready: model=%s", self._model)

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Claude and return the text response.

        Raises:
            LLMServiceError: On API error or empty response.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            if not text:
                raise LLMServiceError("Claude returned an empty response.")
            logger.debug("LLM response length: %d chars", len(text))
            return text.strip()
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.exception("Claude API call failed")
            raise LLMServiceError(f"Claude API error: {exc}") from exc
