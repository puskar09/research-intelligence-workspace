"""
SQLAlchemy engine and session management.

Uses a synchronous psycopg2 connection (simple, no async complexity for MVP).

get_db() is a FastAPI dependency that yields a session and guarantees
cleanup regardless of success or error.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.settings import settings

engine = create_engine(
    settings.database_url(),
    # Keep a small connection pool — fine for local dev.
    pool_pre_ping=True,  # avoids "server closed connection" on idle connections
    echo=False,          # set True to log all SQL statements during debugging
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency.

    Usage:
        from backend.db.database import get_db
        from sqlalchemy.orm import Session
        from fastapi import Depends

        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
