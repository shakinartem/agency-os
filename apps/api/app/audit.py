"""Helpers for durable application audit events."""
from __future__ import annotations

import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import AuditEvent, User


async def record_audit(
    db: AsyncSession,
    *,
    actor: User | None,
    action: str,
    project_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    row = AuditEvent(
        actor_user_id=actor.id if actor else None,
        project_id=project_id,
        action=action[:120],
        entity_type=entity_type[:80] if entity_type else None,
        entity_id=str(entity_id)[:255] if entity_id is not None else None,
        summary=summary,
        metadata_json=metadata or {},
    )
    db.add(row)
    await db.flush()
    return row
