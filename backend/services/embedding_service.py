"""
EmbeddingService — isolated embedding layer for the Research Intelligence Workspace.

Model: sentence-transformers/all-MiniLM-L6-v2
Dimension: 384
Distance metric used for retrieval: cosine (pgvector <=> operator)

Design principles:
- Model is loaded exactly once (at module import time) and reused.
- The actual model name and dimension are exposed as constants so the
  rest of the application can reference them without hard-coding strings.
- Replacing the model only requires changing MODEL_NAME here; the dimension
  constant will update automatically and init_db will alter the column.
- embed_texts() uses the library's built-in batching for efficiency.
"""

import logging
from typing import Final

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MODEL_NAME: Final[str] = "all-MiniLM-L6-v2"

# Loaded once; sentence-transformers caches models in ~/.cache/huggingface
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info(
            "Model loaded. Embedding dimension: %d",
            _model.get_embedding_dimension(),
        )
    return _model


def embedding_dimension() -> int:
    """Return the dimension of the vectors produced by the current model."""
    return _get_model().get_embedding_dimension()


def embed_text(text: str) -> list[float]:
    """
    Embed a single string.

    Returns a list[float] of length `embedding_dimension()`.
    """
    model = _get_model()
    vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """
    Embed a list of strings, processing them in batches.

    Args:
        texts:      Strings to embed.
        batch_size: Number of texts per batch sent to the model.

    Returns:
        List of float vectors, one per input string, in the same order.
    """
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]
