"""Content Factory orchestration API."""

import uuid
from typing import Any

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BrandProfile, ExportDelivery, GenerationRun, Project, Rubric, User

from ..config import config
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.factory import BrandProfileUpsert, RubricCreate, RunCreate

router = APIRouter(prefix="/factory", tags=["content-factory"])
queue = Celery("content_factory_api", broker=config.redis_url)


def _json(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif hasattr(value, "value"):
            value = value.value
        data[column.name] = value
    return data


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    body: RunCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc

    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(404, "Project not found")

    options = {
        **body.options,
        "use_research": body.use_research,
        "generate_media": body.generate_media,
        "auto_export": body.auto_export,
    }
    run = GenerationRun(
        project_id=project_id,
        task=body.task,
        content_type=body.content_type,
        platforms=body.platforms,
        options=options,
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    queue.send_task("content_factory.process_run", args=[str(run.id)])
    return _json(run)


@router.get("/runs")
async def list_runs(
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(GenerationRun).order_by(GenerationRun.created_at.desc()).limit(200)
    if project_id:
        stmt = stmt.where(GenerationRun.project_id == uuid.UUID(project_id))
    rows = (await db.execute(stmt)).scalars().all()
    return [_json(row) for row in rows]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    run = await db.scalar(select(GenerationRun).where(GenerationRun.id == run_id))
    if not run:
        raise HTTPException(404, "Generation run not found")
    return _json(run)


@router.get("/brand/{project_id}")
async def get_brand_profile(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = await db.scalar(select(BrandProfile).where(BrandProfile.project_id == project_id))
    return _json(row) if row else None


@router.put("/brand/{project_id}")
async def upsert_brand_profile(
    project_id: uuid.UUID,
    body: BrandProfileUpsert,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = await db.scalar(select(BrandProfile).where(BrandProfile.project_id == project_id))
    if row is None:
        row = BrandProfile(project_id=project_id, **body.model_dump())
        db.add(row)
    else:
        for key, value in body.model_dump().items():
            setattr(row, key, value)
    await db.flush()
    await db.refresh(row)
    return _json(row)


@router.get("/rubrics")
async def list_rubrics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Rubric).where(Rubric.project_id == project_id, Rubric.active.is_(True)).order_by(Rubric.created_at.desc())
    )).scalars().all()
    return [_json(row) for row in rows]


@router.post("/rubrics", status_code=status.HTTP_201_CREATED)
async def create_rubric(
    body: RubricCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = Rubric(
        project_id=uuid.UUID(body.project_id),
        name=body.name,
        description=body.description,
        goal=body.goal,
        content_types=body.content_types,
        platforms=body.platforms,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return _json(row)


@router.get("/outbox")
async def list_outbox(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ExportDelivery).order_by(ExportDelivery.created_at.desc()).limit(200)
    if project_id:
        from database.models import ContentItem
        stmt = stmt.join(ContentItem, ContentItem.id == ExportDelivery.content_item_id).where(ContentItem.project_id == project_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_json(row) for row in rows]
