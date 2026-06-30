"""Alembic environment configuration.

Loads all ORM models so that autogenerate can detect schema changes.
Uses synchronous driver (psycopg2) for Alembic, even if the app uses asyncpg.

COMPLETELY self-contained — does NOT rely on os.environ to avoid Windows
environment block corruption from non-ASCII .env comment characters.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

# ── Locate project root (4 levels up from alembic/env.py) ───────────────────
_this_file = Path(__file__).resolve()
_alembic_dir = _this_file.parent          # .../alembic/
_db_pkg_dir = _alembic_dir.parent         # .../database/
_packages_dir = _db_pkg_dir.parent        # .../packages/
_project_root = _packages_dir.parent      # .../agency-os/

# ── Ensure the packages directory is on sys.path ───────────────────────────
sys.path.insert(0, str(_packages_dir))

# ── Read DATABASE_URL from .env manually (ONE variable only) ───────────────
_dotenv_path = _project_root / ".env"
print(f"[alembic/env.py] .env path: {_dotenv_path}", file=sys.stderr)
print(f"[alembic/env.py] .env exists: {_dotenv_path.exists()}", file=sys.stderr)

_raw_url = ""
if _dotenv_path.exists():
    with open(_dotenv_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                _raw_url = line.split("=", 1)[1].strip().strip("\"'")
                break

if not _raw_url:
    _raw_url = "postgresql://agency:agency_secret@localhost:5432/agency_os"
    print(f"[alembic/env.py] DATABASE_URL was empty, using hardcoded fallback", file=sys.stderr)

# Sanitise: replace asyncpg with psycopg2 for synchronous Alembic
_sync_url = _raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
_sync_url = _sync_url.replace("postgresql+aiosqlite://", "sqlite:///")
_sync_url = _sync_url.encode("ascii", errors="ignore").decode("ascii")
# In Docker, hostname MUST be "postgres" — do NOT rewrite to localhost
print(f"[alembic/env.py] Sync URL: {_sync_url!r}", file=sys.stderr)

# ── Set os.environ so DatabaseConfig (pydantic-settings) picks it up ────────
os.environ["DATABASE_URL"] = _sync_url

# ── Import models (triggers lazy async engine creation via DatabaseConfig) ──
from database.base import Base
from database.models import *  # noqa: F401, F403

# ── Alembic config ──────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live DB."""
    # Build URL via structured object to bypass Windows env encoding issues
    from urllib.parse import urlparse
    parsed = urlparse(_sync_url)
    conn_url = URL.create(
        drivername="postgresql+psycopg2",
        username=parsed.username or "agency",
        password=parsed.password or "agency_secret",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/") if parsed.path else "agency_os",
    )
    print(f"[alembic/env.py] conn_url: {conn_url!r}", file=sys.stderr)
    connectable = create_engine(
        conn_url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()