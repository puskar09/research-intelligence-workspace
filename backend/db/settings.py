"""
Database settings — reads from environment variables / .env file.

All application code should import Settings from here rather than
reading os.environ directly. This keeps the config surface in one place
and makes it easy to swap values per environment.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file).
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)


class Settings:
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "riw")
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "riw_user")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "riw_password")
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.environ.get("POSTGRES_PORT", "5432")

    @classmethod
    def database_url(cls) -> str:
        """
        Synchronous psycopg2 DSN used by SQLAlchemy.

        Format: postgresql+psycopg2://user:password@host:port/dbname
        """
        return (
            f"postgresql+psycopg2://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}"
            f"@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
        )


settings = Settings()
