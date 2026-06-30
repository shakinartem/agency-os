"""CRUD /publications."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import Publication, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.publication import PublicationCreate, PublicationRead, PublicationUpdate

router = APIRouter(prefix="/publications", tags=["publications"])


@router.get("/", response_model=list[PublicationRead])
async def list_publications(
    project_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Publication)
    if project_id:
        stmt = stmt.where(Publication.project_id == uuid.UUID(project_id))
    if status:
        stmt = stmt.where(Publication.status == status)
    stmt = stmt.order_by(Publication.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{pub_id}", response_model=PublicationRead)
async def get_publication(
    pub_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Publication).where(Publication.id == pub_id))
    pub = result.scalar_one_or_none()
    if not pub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Publication not found")
    return pub


@router.post("/", response_model=PublicationRead, status_code=status.HTTP_201_CREATED)
async def create_publication(
    body: PublicationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    pub = Publication(**body.model_dump())
    db.add(pub)
    await db.flush()
    await db.refresh(pub)
    return pub


@router.put("/{pub_id}", response_model=PublicationRead)
async def update_publication(
    pub_id: uuid.UUID,
    body: PublicationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(Publication).where(Publication.id == pub_id))
    pub = result.scalar_one_or_none()
    if not pub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Publication not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pub, field, value)
    await db.flush()
    await db.refresh(pub)
    return pub


@router.delete("/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_publication(
    pub_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Publication).where(Publication.id == pub_id))
    pub = result.scalar_one_or_none()
    if not pub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Publication not found")
    await db.delete(pub)
