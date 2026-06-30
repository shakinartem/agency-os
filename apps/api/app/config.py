"""App-level config — reads from environment / .env."""

from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Centralised configuration for the FastAPI application."""

    # ── General ──────────────────────────────────────────
    app_name: str = "Agency OS API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Secrets ──────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # ── Database ─────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./agency_os.db"

    # ── CORS ─────────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    model_config = {"env_prefix": "", "extra": "ignore"}


config = AppConfig()
