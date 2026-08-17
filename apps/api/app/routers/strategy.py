"""Content strategy and AI rubric API."""

import uuid
from typing import Any

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GenerationRun, Project, Rubric, User

from ..config import config
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.factory import RubricGenerateRequest

router = APIRouter(prefix="/strategy", tags=["content-strategy"])
queue = Celery("content_strategy_api", broker=config.redis_url)


def _json(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif hasattr(value, "value"):
            value = value.value
        result[column.name] = value
    return result


@router.post("/rubrics/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_rubrics(
    body: RubricGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")

    run = GenerationRun(
        project_id=project_id,
        task=f"Generate reusable content rubrics. Strategy goal: {body.goal}",
        content_type="rubric",
        platforms=body.platforms,
        options={
            "strategy_goal": body.goal,
            "rubric_count": body.count,
            "use_research": body.use_research,
            "generate_media": False,
            "auto_export": False,
        },
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    response = _json(run)
    await db.commit()
    queue.send_task("content_factory.generate_rubrics", args=[str(run.id)])
    return response


@router.get("/rubrics")
async def list_strategy_rubrics(
    project_id: uuid.UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Rubric).where(Rubric.project_id == project_id)
    if not include_inactive:
        stmt = stmt.where(Rubric.active.is_(True))
    stmt = stmt.order_by(Rubric.active.desc(), Rubric.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_json(row) for row in rows]


@router.post("/rubrics/{rubric_id}/archive")
async def archive_rubric(
    rubric_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    row = await db.scalar(select(Rubric).where(Rubric.id == rubric_id))
    if not row:
        raise HTTPException(404, "Rubric not found")
    row.active = False
    await db.flush()
    return _json(row)
