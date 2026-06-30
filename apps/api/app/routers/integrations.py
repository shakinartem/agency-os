"""CRUD /integrations + healthcheck + sync."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import IntegrationHealth, UserRole
from database.models import IntegrationConfig, IntegrationLog, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.integration import (
    IntegrationConfigCreate,
    IntegrationConfigRead,
    IntegrationConfigUpdate,
    IntegrationLogRead,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=list[IntegrationConfigRead])
async def list_integrations(
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(IntegrationConfig)
    if project_id:
        stmt = stmt.where(IntegrationConfig.project_id == uuid.UUID(project_id))
    stmt = stmt.order_by(IntegrationConfig.service_name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{int_id}", response_model=IntegrationConfigRead)
async def get_integration(
    int_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == int_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return cfg


@router.post("/", response_model=IntegrationConfigRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    body: IntegrationConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    cfg = IntegrationConfig(**body.model_dump())
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.put("/{int_id}", response_model=IntegrationConfigRead)
async def update_integration(
    int_id: uuid.UUID,
    body: IntegrationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == int_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.delete("/{int_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    int_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == int_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")
    await db.delete(cfg)


# ── Healthcheck ──────────────────────────────────────────


@router.post("/{int_id}/healthcheck")
async def integration_healthcheck(
    int_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == int_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Mock: ping the base_url; in production make a real HTTP request
    healthy = cfg.base_url is not None
    cfg.health_status = IntegrationHealth.healthy if healthy else IntegrationHealth.down
    cfg.last_error = None if healthy else "Base URL not configured"
    await db.flush()
    await db.refresh(cfg)
    return {
        "id": str(cfg.id),
        "service": cfg.service_name,
        "health": cfg.health_status.value,
    }


# ── Sync ─────────────────────────────────────────────────


@router.post("/{int_id}/sync")
async def integration_sync(
    int_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == int_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Integration not found")

    now = datetime.now(timezone.utc).isoformat()

    # Mock sync log
    log = IntegrationLog(
        integration_config_id=cfg.id,
        action="sync",
        status="success",
        payload={"trigger": "manual"},
        created_at=now,
    )
    cfg.last_sync_at = now
    cfg.last_error = None
    db.add(log)
    await db.flush()

    return {
        "message": f"Sync triggered for {cfg.service_name}",
        "last_sync_at": cfg.last_sync_at,
    }


# ── Logs ─────────────────────────────────────────────────


@router.get("/{int_id}/logs", response_model=list[IntegrationLogRead])
async def list_integration_logs(
    int_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(IntegrationLog)
        .where(IntegrationLog.integration_config_id == int_id)
        .order_by(IntegrationLog.created_at.desc())
    )
    return result.scalars().all()
