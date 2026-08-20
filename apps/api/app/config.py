"""Application configuration for Content Factory."""
from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class AppConfig(BaseSettings):
    app_name: str = "Content Factory API"
    app_version: str = "0.4.0"
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "app_env"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG", "DEBUG", "debug"))

    # HMAC/privacy secret for sessions and server-side identifiers.
    secret_key: str = "change-me-in-production"

    # Revocable opaque browser/API sessions.
    session_cookie_name: str = "cf_session"
    session_ttl_minutes: int = 8 * 60
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 15 * 60

    database_url: str = "sqlite+aiosqlite:///./agency_os.db"
    redis_url: str = "redis://localhost:6380/0"
    cors_origins: list[str] = ["http://localhost:3010"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    api_docs_enabled: bool = True

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-5.6"
    image_api_url: str | None = None
    image_api_key: str | None = None
    image_model: str = "gpt-image-1.5"

    autoposter_url: str | None = None
    autoposter_token: str | None = None
    performance_ingest_token: str | None = None
    task_outbox_dispatch_batch: int = 50

    quality_threshold: float = 0.87
    factuality_threshold: float = 0.95
    brand_voice_threshold: float = 0.85
    max_revision_attempts: int = 2

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"prod", "production"}

    @model_validator(mode="after")
    def validate_production_safety(self):
        if not self.is_production:
            return self
        errors: list[str] = []
        if not self.secret_key or self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be a random secret of at least 32 characters")
        if self.debug:
            errors.append("APP_DEBUG must be false in production")
        if not self.session_cookie_secure:
            errors.append("SESSION_COOKIE_SECURE must be true in production")
        if "*" in self.cors_origins:
            errors.append("CORS_ORIGINS cannot contain '*' in production")
        if "*" in self.allowed_hosts or not self.allowed_hosts:
            errors.append("ALLOWED_HOSTS must explicitly list production hosts")
        if self.database_url.startswith("sqlite"):
            errors.append("Production DATABASE_URL must use PostgreSQL")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        return self

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
    }


config = AppConfig()
