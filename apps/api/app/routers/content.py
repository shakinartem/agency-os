"""Canonical content API for the review workspace.

Manual edits are versioned instead of silently overwriting AI output. Every operation is
project-scoped to prevent cross-project IDOR/data leakage.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import ContentStatus, ContentType
from database.models import ContentItem, ContentVersion, Project, User

from ..access import accessible_project_ids, ensure_project_capability
from ..audit import record_audit
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.content import ContentItemCreate, ContentItemRead, ContentItemUpdate

router = APIRouter(prefix="/content", tags=["content"])


def _content_type(value: str) -> ContentType:
    try: return ContentType(value)
    except ValueError as exc: raise HTTPException(400, f"Unsupported content type: {value}") from exc


def _content_status(value: str) -> ContentStatus:
    try: return ContentStatus(value)
    except ValueError as exc: raise HTTPException(400, f"Unsupported content status: {value}") from exc


@router.get("/", response_model=list[ContentItemRead])
async def list_content_items(project_id: str | None = None, status_filter: str | None = None,
                             db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ContentItem)
    if project_id:
        try: parsed_project_id = uuid.UUID(project_id)
        except ValueError as exc: raise HTTPException(400, "Invalid project_id") from exc
        await ensure_project_capability(db, user, parsed_project_id, "content:read")
        stmt = stmt.where(ContentItem.project_id == parsed_project_id)
    else:
        ids = await accessible_project_ids(db, user)
        if ids is not None:
            if not ids: return []
            stmt = stmt.where(ContentItem.project_id.in_(ids))
    if status_filter: stmt = stmt.where(ContentItem.status == _content_status(status_filter))
    return (await db.execute(stmt.order_by(ContentItem.created_at.desc()).limit(500))).scalars().all()


@router.get("/{item_id}", response_model=ContentItemRead)
async def get_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item: raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:read")
    return item


@router.post("/", response_model=ContentItemRead, status_code=status.HTTP_201_CREATED)
async def create_content_item(body: ContentItemCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try: project_id = uuid.UUID(body.project_id)
    except ValueError as exc: raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)): raise HTTPException(404, "Project not found")
    await ensure_project_capability(db, user, project_id, "content:edit")
    item = ContentItem(project_id=project_id, type=_content_type(body.type), status=_content_status(body.status),
                       title=body.title, body=body.body, task=body.task, topic=body.topic, goal=body.goal,
                       platforms=body.platforms, current_version=1, structured_json={"title": body.title, "body": body.body})
    db.add(item); await db.flush()
    db.add(ContentVersion(content_item_id=item.id, version=1, stage="manual_create", title=item.title, body=item.body,
                          structured_json=item.structured_json, created_by=f"user:{user.id}"))
    await record_audit(db, actor=user, action="content.create", project_id=project_id, entity_type="content_item", entity_id=item.id, metadata={"content_version": 1})
    await db.flush(); await db.refresh(item); return item


@router.put("/{item_id}", response_model=ContentItemRead)
async def update_content_item(item_id: uuid.UUID, body: ContentItemUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item: raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:edit")
    changes = body.model_dump(exclude_unset=True)
    if "type" in changes and changes["type"] is not None: changes["type"] = _content_type(changes["type"])
    if "status" in changes and changes["status"] is not None: changes["status"] = _content_status(changes["status"])
    for field, value in changes.items(): setattr(item, field, value)
    item.current_version += 1
    item.structured_json = {**(item.structured_json or {}), "title": item.title, "body": item.body, "hook": item.hook,
                            "cta": item.cta, "hashtags": item.hashtags or [], "visual_prompt": item.visual_prompt}
    db.add(ContentVersion(content_item_id=item.id, version=item.current_version, stage="manual_edit", title=item.title,
                          body=item.body, structured_json=item.structured_json, created_by=f"user:{user.id}"))
    await record_audit(db, actor=user, action="content.edit", project_id=item.project_id, entity_type="content_item", entity_id=item.id, metadata={"content_version": item.current_version, "fields": sorted(changes)})
    await db.flush(); await db.refresh(item); return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_content_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Archive instead of physically deleting valuable learning data."""
    item = await db.scalar(select(ContentItem).where(ContentItem.id == item_id))
    if not item: raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:edit")
    item.status = ContentStatus.archived; item.current_version += 1
    db.add(ContentVersion(content_item_id=item.id, version=item.current_version, stage="archive", title=item.title,
                          body=item.body, structured_json=item.structured_json or {}, created_by=f"user:{user.id}"))
    await record_audit(db, actor=user, action="content.archive", project_id=item.project_id, entity_type="content_item", entity_id=item.id, metadata={"content_version": item.current_version})
