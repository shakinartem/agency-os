"""CRUD /content (ContentItems + ContentPlans)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import ContentItem, ContentPlan, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.content import ContentItemCreate, ContentItemRead, ContentItemUpdate, ContentPlanRead

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/", response_model=list[ContentItemRead])
async def list_content_items(
    project_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ContentItem)
    if project_id:
        stmt = stmt.where(ContentItem.project_id == uuid.UUID(project_id))
    if status:
        stmt = stmt.where(ContentItem.status == status)
    stmt = stmt.order_by(ContentItem.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{item_id}", response_model=ContentItemRead)
async def get_content_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")
    return item


@router.post("/", response_model=ContentItemRead, status_code=status.HTTP_201_CREATED)
async def create_content_item(
    body: ContentItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    item = ContentItem(**body.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=ContentItemRead)
async def update_content_item(
    item_id: uuid.UUID,
    body: ContentItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")
    await db.delete(item)


# ── Content Plans ────────────────────────────────────────


@router.get("/plans", response_model=list[ContentPlanRead])
async def list_content_plans(
    project_id: str | None = None,
    month: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ContentPlan)
    if project_id:
        stmt = stmt.where(ContentPlan.project_id == uuid.UUID(project_id))
    if month:
        stmt = stmt.where(ContentPlan.month == month)
    stmt = stmt.order_by(ContentPlan.month.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
