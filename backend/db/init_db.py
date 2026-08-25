"""
Database initialisation.

Called once at FastAPI startup (via main.py lifespan).

Responsibilities:
1. Enable the pgvector extension.
2. Create all tables if they do not already exist.
3. Phase 3: Add the embedding column to chunks if it does not exist yet.
   This is an idempotent ALTER TABLE that is safe to run on an already-populated
   database — existing rows get NULL embedding and can be backfilled separately.

Why not Alembic?
  The schema is still stabilising across phases and the Docker workflow makes
  recreation trivial. Alembic will be added when the schema is stable and
  production deployments need tracked incremental migrations.
"""

import logging

from sqlalchemy import text

from backend.db.database import engine
from backend.db.orm_models import Base, EMBEDDING_DIM

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Initialise the database schema. Safe to call multiple times.

    Order matters:
      1. Extension first (Vector type depends on it).
      2. create_all second (creates tables without the embedding column
         if they already exist — that is fine, step 3 adds it).
      3. ALTER TABLE third — adds the column to existing tables idempotently.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension ensured.")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created (or already existed).")

    # Idempotent column addition for Phase 3 — safe on pre-existing tables.
    with engine.begin() as conn:
        conn.execute(text(
            f"ALTER TABLE chunks "
            f"ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})"
        ))
        logger.info(
            "chunks.embedding column ensured (dim=%d).", EMBEDDING_DIM
        )
