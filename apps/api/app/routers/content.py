"""Canonical content API for the review workspace.

Manual edits are versioned instead of silently overwriting AI output.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import ContentStatus, ContentType, UserRole
from database.models import ContentItem, ContentVersion, Project, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.content import ContentItemCreate, ContentItemRead, ContentItemUpdate

router = APIRouter(prefix="/content", tags=["content"])


def _content_type(value: str) -> ContentType:
    try:
        return ContentType(value)
    except ValueError as exc:
        raise HTTPException(400, f"Unsupported content type: {value}") from exc


def _content_status(value: str) -> ContentStatus:
    try:
        return ContentStatus(value)
    except ValueError as exc:
        raise HTTPException(400, f"Unsupported content status: {value}") from exc


@router.get("/", response_model=list[ContentItemRead])
async def list_content_items(
    project_id: str | None = None,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ContentItem)
    if project_id:
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid project_id") from exc
        stmt = stmt.where(ContentItem.project_id == parsed_project_id)
    if status_filter:
        stmt = stmt.where(ContentItem.status == _content_status(status_filter))
    stmt = stmt.order_by(ContentItem.created_at.desc()).limit(500)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{item_id}", response_model=ContentItemRead)
async def get_content_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")
    return item


@router.post("/", response_model=ContentItemRead, status_code=status.HTTP_201_CREATED)
async def create_content_item(
    body: ContentItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")

    item = ContentItem(
        project_id=project_id,
        type=_content_type(body.type),
        status=_content_status(body.status),
        title=body.title,
        body=body.body,
        task=body.task,
        topic=body.topic,
        goal=body.goal,
        platforms=body.platforms,
        current_version=1,
        structured_json={"title": body.title, "body": body.body},
    )
    db.add(item)
    await db.flush()
    db.add(ContentVersion(
        content_item_id=item.id,
        version=1,
        stage="manual_create",
        title=item.title,
        body=item.body,
        structured_json=item.structured_json,
        created_by=f"user:{user.id}",
    ))
    await db.flush()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=ContentItemRead)
async def update_content_item(
    item_id: uuid.UUID,
    body: ContentItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")

    changes = body.model_dump(exclude_unset=True)
    if "type" in changes and changes["type"] is not None:
        changes["type"] = _content_type(changes["type"])
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _content_status(changes["status"])

    for field, value in changes.items():
        setattr(item, field, value)

    item.current_version += 1
    item.structured_json = {
        **(item.structured_json or {}),
        "title": item.title,
        "body": item.body,
        "hook": item.hook,
        "cta": item.cta,
        "hashtags": item.hashtags or [],
        "visual_prompt": item.visual_prompt,
    }
    db.add(ContentVersion(
        content_item_id=item.id,
        version=item.current_version,
        stage="manual_edit",
        title=item.title,
        body=item.body,
        structured_json=item.structured_json,
        created_by=f"user:{user.id}",
    ))
    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_content_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin)),
):
    """Archive instead of physically deleting valuable learning data."""
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Content item not found")
    item.status = ContentStatus.archived
    item.current_version += 1
    db.add(ContentVersion(
        content_item_id=item.id,
        version=item.current_version,
        stage="archive",
        title=item.title,
        body=item.body,
        structured_json=item.structured_json or {},
        created_by=f"user:{user.id}",
    ))
