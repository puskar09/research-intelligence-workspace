"""
Research Intelligence Workspace — FastAPI backend entry point.

Run with:
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI

from backend.api.sources import router as sources_router

app = FastAPI(
    title="Research Intelligence Workspace",
    description="Backend API for the Research Intelligence Workspace pipeline.",
    version="0.1.0",
)

# --- Routers ---
app.include_router(sources_router, prefix="/api/sources", tags=["sources"])


# --- Health ---
@app.get("/health", tags=["health"], summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}