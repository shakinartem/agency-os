"""Database session dependency for FastAPI route handlers."""

from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.base import async_session as _raw_session
from database.models import *  # noqa: F401, F403 — ensure all models are importable

# Re-export for convenience
from database.models import (
    User,
    Project,
    Lead,
    LeadEvent,
    Conversation,
    ConversationMessage,
    ContentItem,
    ContentPlan,
    Publication,
    ReportSnapshot,
    IntegrationConfig,
    IntegrationLog,
    SystemSetting,
)

__all__ = [
    "get_db",
    "User",
    "Project",
    "Lead",
    "LeadEvent",
    "Conversation",
    "ConversationMessage",
    "ContentItem",
    "ContentPlan",
    "Publication",
    "ReportSnapshot",
    "IntegrationConfig",
    "IntegrationLog",
    "SystemSetting",
]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with _raw_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
