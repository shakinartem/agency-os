"""Project CRUD, membership administration and scoped authorization."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import Project, ProjectMembership, User

from ..audit import record_audit
from ..access import PROJECT_ROLES, ROLE_CAPABILITIES, accessible_project_ids, ensure_project_capability
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


class MembershipUpdate(BaseModel):
    role: str
    capabilities: list[str] = Field(default_factory=list)


@router.get("/", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    ids = await accessible_project_ids(db, user)
    stmt = select(Project).order_by(Project.created_at)
    if ids is not None:
        if not ids:
            return []
        stmt = stmt.where(Project.id.in_(ids))
    return (await db.execute(stmt)).scalars().all()


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "project:view")
    proj = await db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    if await db.scalar(select(Project.id).where(Project.slug == body.slug)):
        raise HTTPException(409, "Slug already exists")
    proj = Project(**body.model_dump())
    db.add(proj)
    await db.flush()
    db.add(ProjectMembership(project_id=proj.id, user_id=user.id, role="owner", capabilities=[]))
    await record_audit(db, actor=user, action="project.create", project_id=proj.id, entity_type="project", entity_id=proj.id)
    await db.flush()
    await db.refresh(proj)
    return proj


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "project:manage")
    proj = await db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(proj, field, value)
    await record_audit(db, actor=user, action="project.update", project_id=proj.id, entity_type="project", entity_id=proj.id, metadata={"fields": sorted(changes)})
    await db.flush(); await db.refresh(proj)
    return proj


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "project:manage")
    proj = await db.get(Project, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    if proj.status == "archived":
        return
    proj.status = "archived"
    await record_audit(db, actor=user, action="project.archive", project_id=proj.id, entity_type="project", entity_id=proj.id)


@router.get("/{project_id}/members")
async def list_members(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "members:manage")
    rows = (
        await db.execute(
            select(ProjectMembership, User)
            .join(User, User.id == ProjectMembership.user_id)
            .where(ProjectMembership.project_id == project_id)
            .order_by(User.email)
        )
    ).all()
    return [
        {
            "user_id": str(member.user_id), "email": target.email, "name": target.name,
            "role": member.role, "capabilities": member.capabilities or [],
        }
        for member, target in rows
    ]


@router.put("/{project_id}/members/{user_id}")
async def upsert_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MembershipUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "members:manage")
    role = body.role.strip().lower()
    if role not in PROJECT_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(PROJECT_ROLES)}")
    known_capabilities = set().union(*ROLE_CAPABILITIES.values())
    requested_capabilities = sorted(set(value.strip() for value in body.capabilities if value.strip()))
    unknown = sorted(set(requested_capabilities) - known_capabilities)
    if unknown:
        raise HTTPException(400, f"Unknown project capabilities: {unknown}")
    target_user = await db.get(User, user_id)
    if target_user is None:
        raise HTTPException(404, "User not found")
    if not target_user.is_active:
        raise HTTPException(409, "Inactive users cannot be added to a project")
    row = await db.scalar(select(ProjectMembership).where(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id))
    if row is not None and row.role == "owner" and role != "owner":
        owners = (
            await db.execute(select(ProjectMembership.id).where(ProjectMembership.project_id == project_id, ProjectMembership.role == "owner"))
        ).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(409, "Assign another project owner before demoting the last owner")
    if row is None:
        row = ProjectMembership(project_id=project_id, user_id=user_id, role=role, capabilities=requested_capabilities)
        db.add(row)
    else:
        row.role = role
        row.capabilities = requested_capabilities
    await record_audit(db, actor=user, action="project.member.upsert", project_id=project_id, entity_type="user", entity_id=user_id, metadata={"role": row.role, "capabilities": row.capabilities or []})
    await db.flush()
    return {"user_id": str(user_id), "project_id": str(project_id), "role": row.role, "capabilities": row.capabilities or []}


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "members:manage")
    row = await db.scalar(select(ProjectMembership).where(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id))
    if row is None:
        raise HTTPException(404, "Membership not found")
    if row.role == "owner":
        owners = (
            await db.execute(select(ProjectMembership.id).where(ProjectMembership.project_id == project_id, ProjectMembership.role == "owner"))
        ).scalars().all()
        if len(owners) <= 1:
            raise HTTPException(409, "Cannot remove the last project owner")
    await record_audit(db, actor=user, action="project.member.remove", project_id=project_id, entity_type="user", entity_id=user_id, metadata={"role": row.role})
    await db.delete(row)
