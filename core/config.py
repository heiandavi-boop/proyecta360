"""Centralized application configuration.

Single source of truth for environment-driven settings. Replaces the scattered
``os.getenv`` calls. Read once at import time as the module-level ``settings``
singleton. Env var names are kept backwards-compatible via ``validation_alias``
(e.g. the long-standing ``PROYECTA360_DB``).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the core/ package directory.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Persistence
    db_path: Path = Field(default=BASE_DIR / "proyecta360.db", validation_alias="PROYECTA360_DB")
    # Reserved for the future PostgreSQL migration (Fase 5). When set, takes
    # precedence over db_path for Alembic's connection URL.
    database_url: Optional[str] = Field(default=None, validation_alias="PROYECTA360_DATABASE_URL")

    # HTTP / CORS
    cors_origins_raw: str = Field(
        default="http://127.0.0.1:8000,http://localhost:8000",
        validation_alias="PROYECTA360_CORS_ORIGINS",
    )

    # Runtime
    env: str = Field(default="local", validation_alias="PROYECTA360_ENV")
    log_level: str = Field(default="INFO", validation_alias="PROYECTA360_LOG_LEVEL")
    seed_on_startup: bool = Field(default=True, validation_alias="PROYECTA360_SEED_ON_STARTUP")

    # Reserved for auth (Fase 4)
    secret_key: Optional[str] = Field(default=None, validation_alias="PROYECTA360_SECRET_KEY")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def alembic_url(self) -> str:
        """SQLAlchemy URL used by Alembic. Falls back to the local SQLite file."""
        return self.database_url or f"sqlite:///{self.db_path}"


settings = Settings()
