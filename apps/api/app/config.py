"""App-level config that reads from environment variables and .env."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"


class AppConfig(BaseSettings):
    """Centralised configuration for the FastAPI application."""

    app_name: str = "Agency OS API"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "app_env"))
    debug: bool = Field(default=False, validation_alias=AliasChoices("APP_DEBUG", "DEBUG", "debug"))

    secret_key: str = "change-me-in-production"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    database_url: str = "sqlite+aiosqlite:///./agency_os.db"
    cors_origins: list[str] = ["*"]

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
    }


config = AppConfig()
