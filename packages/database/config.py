"""Pydantic-based settings for database configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class DatabaseConfig(BaseSettings):
    """Read DB connection parameters from the environment."""

    database_url: str = "sqlite+aiosqlite:///./agency_os.db"
    echo: bool = False

    model_config = {
        "env_prefix": "",
        "extra": "ignore",
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
    }
