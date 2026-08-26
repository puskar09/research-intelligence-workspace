"""
Research Intelligence Workspace — FastAPI backend entry point.

Run with:
    uvicorn backend.main:app --reload --port 8001

Phase 3: search router mounted at /api/search.
         Embedding model dimension is verified against DB schema at startup.
Phase 4: RAG router mounted at /api/rag.
         Requires GOOGLE_API_KEY in .env.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.rag import router as rag_router
from backend.api.research import router as research_router
from backend.api.search import router as search_router
from backend.api.sources import router as sources_router
from backend.db.init_db import init_db
from backend.db.orm_models import EMBEDDING_DIM
from backend.services.embedding_service import embedding_dimension

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up -- initialising database...")
    init_db()

    # Verify the live model dimension matches the DB schema.
    live_dim = embedding_dimension()
    if live_dim != EMBEDDING_DIM:
        raise RuntimeError(
            f"Embedding model dimension mismatch: model={live_dim}, "
            f"DB schema={EMBEDDING_DIM}. "
            "Update EMBEDDING_DIM in orm_models.py or change the model."
        )
    logger.info("Embedding model verified: dim=%d.", live_dim)
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Research Intelligence Workspace",
    description="Backend API for the Research Intelligence Workspace pipeline.",
    version="0.5.0",
    lifespan=lifespan,
)

# --- Routers ---
app.include_router(sources_router, prefix="/api/sources", tags=["sources"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
app.include_router(research_router, prefix="/api/research", tags=["research"])


# --- Health ---
@app.get("/health", tags=["health"], summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}