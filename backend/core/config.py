"""Core Application Configuration.

Centralizes environment variables and application runtime parameters
using Pydantic BaseSettings for robust validation and type safety.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema backed by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Digital Credential Lifecycle Management System"
    APP_ENV: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "dev_secret_key_change_in_production_min_32_bytes_long_12345"

    # Database URLs
    # Async connection for FastAPI application layer
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/credential_db"
    )
    # Sync connection for Alembic migrations and synchronous CLI tools
    SYNC_DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/credential_db"
    )

    # Isolated Test Database URLs (used exclusively by pytest)
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/credential_test_db"
    )
    TEST_DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/credential_test_db"
    )

    # Synthetic Data Defaults
    DEFAULT_SEED: int = 20261022
    SYNTHETIC_LEARNER_COUNT: int = 20000
    SYNTHETIC_COURSE_COUNT: int = 1000
    SYNTHETIC_CREDENTIAL_COUNT: int = 10000
    SYNTHETIC_VERIFICATION_COUNT: int = 5000


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Application Settings."""
    return Settings()


settings = get_settings()
