"""Project Knowledge Base API with project-scoped authorization."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import KnowledgeChunk, KnowledgeDocument, Project, User

from ..access import ensure_project_capability
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.knowledge import KnowledgeTextCreate
from ..services.knowledge import checksum_text, chunk_text, extract_upload, normalize_text

router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])


def _json(row: Any, *, include_content: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        if not include_content and column.name == "content":
            continue
        value = getattr(row, column.name)
        if isinstance(value, uuid.UUID): value = str(value)
        elif hasattr(value, "isoformat"): value = value.isoformat()
        data[column.name] = value
    return data


async def _ensure_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")


async def _ingest(*, db: AsyncSession, project_id: uuid.UUID, name: str, content: str, source_type: str,
                  mime_type: str | None, metadata_json: dict[str, Any] | None = None) -> tuple[KnowledgeDocument, bool]:
    await _ensure_project(db, project_id)
    normalized = normalize_text(content)
    checksum = checksum_text(normalized)
    existing = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.project_id == project_id, KnowledgeDocument.checksum == checksum))
    if existing:
        if existing.status != "active": existing.status = "active"
        return existing, True
    chunks = chunk_text(normalized)
    document = KnowledgeDocument(project_id=project_id, name=name[:500], source_type=source_type[:50], mime_type=mime_type,
                                 checksum=checksum, status="active", char_count=len(normalized), chunk_count=len(chunks),
                                 content=normalized, metadata_json=metadata_json or {})
    db.add(document); await db.flush()
    for position, chunk in enumerate(chunks):
        db.add(KnowledgeChunk(project_id=project_id, document_id=document.id, position=position, content=chunk,
                              token_estimate=max(1, len(chunk) // 4), metadata_json={"document_name": document.name}))
    await db.flush()
    return document, False


@router.get("")
async def list_documents(project_id: uuid.UUID, include_archived: bool = False, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "knowledge:read")
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.project_id == project_id)
    if not include_archived: stmt = stmt.where(KnowledgeDocument.status == "active")
    rows = (await db.execute(stmt.order_by(KnowledgeDocument.created_at.desc()))).scalars().all()
    return [_json(row) for row in rows]


@router.get("/{document_id}")
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    if not document: raise HTTPException(404, "Knowledge document not found")
    await ensure_project_capability(db, user, document.project_id, "knowledge:read")
    result = _json(document); result["preview"] = document.content[:12000]
    return result


@router.post("/text", status_code=status.HTTP_201_CREATED)
async def add_text(body: KnowledgeTextCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try: project_id = uuid.UUID(body.project_id)
    except ValueError as exc: raise HTTPException(400, "Invalid project_id") from exc
    await ensure_project_capability(db, user, project_id, "knowledge:write")
    document, duplicate = await _ingest(db=db, project_id=project_id, name=body.name, content=body.content,
                                        source_type=body.source_type, mime_type="text/plain", metadata_json=body.metadata_json)
    return {**_json(document), "duplicate": duplicate}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(project_id: str = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try: parsed_project_id = uuid.UUID(project_id)
    except ValueError as exc: raise HTTPException(400, "Invalid project_id") from exc
    await ensure_project_capability(db, user, parsed_project_id, "knowledge:write")
    content, mime_type, metadata = await extract_upload(file)
    document, duplicate = await _ingest(db=db, project_id=parsed_project_id, name=file.filename or "Knowledge document",
                                        content=content, source_type="upload", mime_type=mime_type, metadata_json=metadata)
    return {**_json(document), "duplicate": duplicate}


@router.post("/{document_id}/archive")
async def archive_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    if not document: raise HTTPException(404, "Knowledge document not found")
    await ensure_project_capability(db, user, document.project_id, "knowledge:write")
    document.status = "archived"; await db.flush(); return _json(document)


@router.post("/{document_id}/restore")
async def restore_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
    if not document: raise HTTPException(404, "Knowledge document not found")
    await ensure_project_capability(db, user, document.project_id, "knowledge:write")
    document.status = "active"; await db.flush(); return _json(document)
