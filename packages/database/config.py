"""Pydantic-based settings for database configuration."""

from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Read DB connection parameters from the environment.

    Intentionally does NOT auto-load .env — the caller (env.py or app entrypoint)
    is responsible for loading .env so it can sanitise the URL before it reaches
    pydantic-settings.  This avoids encoding issues with non-ASCII characters
    in .env comments.
    """

    database_url: str = "sqlite+aiosqlite:///./agency_os.db"
    echo: bool = False

    model_config = {"env_prefix": "", "extra": "ignore", "env_file": None}
