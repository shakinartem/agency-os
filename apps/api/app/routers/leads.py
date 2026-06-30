"""CRUD /leads + /leads/:id/events."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.enums import UserRole
from database.models import Lead, LeadEvent, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.lead import LeadCreate, LeadEventRead, LeadRead, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/", response_model=list[LeadRead])
async def list_leads(
    project_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Lead)
    if project_id:
        stmt = stmt.where(Lead.project_id == uuid.UUID(project_id))
    if status:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.order_by(Lead.created_at)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.post("/", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    lead = Lead(**body.model_dump())
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.put("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    await db.delete(lead)


# ── Lead Events ──────────────────────────────────────────


@router.get("/{lead_id}/events", response_model=list[LeadEventRead])
async def list_lead_events(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LeadEvent)
        .where(LeadEvent.lead_id == lead_id)
        .order_by(LeadEvent.created_at)
    )
    return result.scalars().all()


@router.post("/{lead_id}/events", response_model=LeadEventRead,
             status_code=status.HTTP_201_CREATED)
async def create_lead_event(
    lead_id: uuid.UUID,
    event_type: str,
    event_data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    from datetime import datetime, timezone
    event = LeadEvent(
        lead_id=lead_id,
        type=event_type,
        data=event_data or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event
