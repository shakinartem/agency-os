"""CRUD /projects."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import Project, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectRead])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).order_by(Project.created_at))
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return proj


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    dup = await db.execute(select(Project).where(Project.slug == body.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Slug already exists")

    proj = Project(**body.model_dump())
    db.add(proj)
    await db.flush()
    await db.refresh(proj)
    return proj


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(proj, field, value)
    await db.flush()
    await db.refresh(proj)
    return proj


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.delete(proj)
