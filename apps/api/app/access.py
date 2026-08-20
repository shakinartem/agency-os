"""Project-scoped capability authorization.

Global admins are break-glass operators. Every non-admin user must have an explicit
ProjectMembership. Capabilities are role defaults plus optional per-membership grants.
"""
from __future__ import annotations

import uuid
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import ProjectMembership, User

PROJECT_ROLES = {"owner", "editor", "reviewer", "viewer"}
ROLE_CAPABILITIES: dict[str, set[str]] = {
    "owner": {
        "project:view", "project:manage", "members:manage",
        "knowledge:read", "knowledge:write", "brand:read", "brand:write",
        "content:read", "content:generate", "content:edit", "content:review", "content:approve",
        "content:publish", "rubric:read", "rubric:write", "performance:view", "performance:manage",
        "router:view", "experiments:view", "experiments:manage", "operations:manage",
    },
    "editor": {
        "project:view", "knowledge:read", "knowledge:write", "brand:read", "brand:write",
        "content:read", "content:generate", "content:edit", "content:review", "content:approve",
        "content:publish", "rubric:read", "rubric:write", "performance:view", "performance:manage",
        "router:view", "experiments:view", "experiments:manage",
    },
    "reviewer": {
        "project:view", "knowledge:read", "brand:read", "content:read", "content:review",
        "content:approve", "rubric:read", "performance:view", "router:view", "experiments:view",
    },
    "viewer": {
        "project:view", "knowledge:read", "brand:read", "content:read", "rubric:read",
        "performance:view", "router:view", "experiments:view",
    },
}


def is_global_admin(user: User) -> bool:
    return user.role == UserRole.admin


async def get_project_membership(
    db: AsyncSession, user: User, project_id: uuid.UUID
) -> ProjectMembership | None:
    return await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )


async def ensure_project_capability(
    db: AsyncSession,
    user: User,
    project_id: uuid.UUID,
    capability: str,
) -> ProjectMembership | None:
    if is_global_admin(user):
        return None
    membership = await get_project_membership(db, user, project_id)
    if membership is None:
        # Do not reveal whether the project exists to an unauthorized caller.
        raise HTTPException(404, "Project not found")
    granted = set(ROLE_CAPABILITIES.get(membership.role, set())) | set(membership.capabilities or [])
    if capability not in granted:
        raise HTTPException(403, f"Project capability required: {capability}")
    return membership


async def ensure_any_project_capability(
    db: AsyncSession,
    user: User,
    project_ids: Iterable[uuid.UUID],
    capability: str,
) -> None:
    for project_id in project_ids:
        await ensure_project_capability(db, user, project_id, capability)


async def accessible_project_ids(db: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """None means global-admin unrestricted access."""
    if is_global_admin(user):
        return None
    return list(
        (
            await db.execute(
                select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id)
            )
        ).scalars().all()
    )
