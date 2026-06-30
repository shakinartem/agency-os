"""SQLAlchemy declarative base, engine, and async session factory.

Engine + session are created lazily so that Alembic (sync) can import
the models without triggering async-engine setup.

Usage:
    from database.base import Base, engine, async_session, get_session
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DatabaseConfig

# ── Declarative base ────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Lazy engine / session factory ───────────────────────────────────────────
# Do NOT create these at import time — Alembic (sync) imports the models
# and would trigger an error if an async engine were created eagerly.

_config: DatabaseConfig | None = None
_engine = None
_session_maker = None


def get_config() -> DatabaseConfig:
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


def get_engine():
    global _engine
    if _engine is None:
        cfg = get_config()
        _engine = create_async_engine(cfg.database_url, echo=cfg.echo)
    return _engine


def get_async_session_maker():
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False,
        )
    return _session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:  # type: ignore[misc]
    """Yield an async session — suitable for FastAPI dependencies / context managers."""
    maker = get_async_session_maker()
    async with maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Module-level lazy accessors for backward compat ─────────────────────────
# ``from database.base import engine`` triggers __getattr__ on first access.


def __getattr__(name: str):
    """Lazy-init ``engine`` and ``async_session`` on first attribute access."""
    if name == "engine":
        return get_engine()
    if name == "async_session":
        return get_async_session_maker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")