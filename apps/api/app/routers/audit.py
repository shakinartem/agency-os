"""Admin-only audit trail API."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.enums import UserRole
from database.models import AuditEvent, User
from ..database import get_db
from ..dependencies import require_role

router = APIRouter(prefix="/audit", tags=["audit"])


def _json(row: AuditEvent) -> dict:
    return {
        "id": str(row.id),
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "project_id": str(row.project_id) if row.project_id else None,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "summary": row.summary,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
async def list_audit_events(
    project_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(max(1, min(limit, 1000)))
    if project_id is not None:
        stmt = stmt.where(AuditEvent.project_id == project_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action[:120])
    return [_json(row) for row in (await db.execute(stmt)).scalars().all()]
