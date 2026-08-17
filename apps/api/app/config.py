"""Application configuration for Content Factory."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class AppConfig(BaseSettings):
    app_name: str = "Content Factory API"
    app_version: str = "0.3.0"
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "app_env"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG", "DEBUG", "debug"))

    secret_key: str = "change-me-in-production"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    database_url: str = "sqlite+aiosqlite:///./agency_os.db"
    redis_url: str = "redis://localhost:6380/0"
    cors_origins: list[str] = ["*"]

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

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
    }


config = AppConfig()
