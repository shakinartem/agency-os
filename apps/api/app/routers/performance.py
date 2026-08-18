"""Downstream performance ingestion, learning signals and generation economics."""

from __future__ import annotations

import hmac
import os
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.generation_economics import aggregate_generation_economics
from database.model_router_cache import mark_model_router_snapshot_stale, schedule_model_router_refresh
from database.models import ContentItem, GenerationRun, GenerationStep, PerformanceSnapshot, ProductionBatchItem, Rubric, User
from database.performance_learning import build_performance_learning_context

from ..config import config
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.factory import PerformanceIngest

router = APIRouter(prefix="/performance", tags=["content-performance"])


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


def _require_ingest_token(token: str | None) -> None:
    configured = config.performance_ingest_token
    if not configured:
        raise HTTPException(503, "Performance ingestion is disabled until PERFORMANCE_INGEST_TOKEN is configured")
    if not token or not hmac.compare_digest(token, configured):
        raise HTTPException(401, "Invalid performance ingest token")


@router.post("/ingest", status_code=202)
async def ingest_performance(
    body: PerformanceIngest,
    x_performance_token: str | None = Header(default=None, alias="X-Performance-Token"),
    db: AsyncSession = Depends(get_db),
):
    _require_ingest_token(x_performance_token)
    try:
        content_id = uuid.UUID(body.content_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid content_id") from exc

    item = await db.scalar(select(ContentItem).where(ContentItem.id == content_id))
    if not item:
        raise HTTPException(404, "Content item not found")

    existing = await db.scalar(
        select(PerformanceSnapshot).where(
            PerformanceSnapshot.source == body.source,
            PerformanceSnapshot.event_id == body.event_id,
        )
    )
    if existing:
        if existing.content_item_id != content_id or existing.external_publication_id != body.external_publication_id:
            raise HTTPException(409, "event_id was already used for a different publication")
        return {"status": "duplicate", "snapshot": _json(existing)}

    row = PerformanceSnapshot(
        project_id=item.project_id,
        content_item_id=item.id,
        source=body.source,
        event_id=body.event_id,
        external_publication_id=body.external_publication_id,
        platform=body.platform,
        metrics=body.metrics,
        captured_at=body.captured_at,
        metadata_json=body.metadata,
    )
    db.add(row)
    await db.flush()

    # Performance is the highest-value new routing evidence. Invalidate the materialized
    # router read-model immediately and enqueue a durable refresh in the same transaction.
    default_model = os.getenv("LLM_MODEL", "gpt-5.6")
    await mark_model_router_snapshot_stale(db, item.project_id, default_model)
    await schedule_model_router_refresh(db, item.project_id)

    await db.refresh(row)
    return {"status": "accepted", "snapshot": _json(row)}


@router.get("/content/{content_id}")
async def content_performance(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.content_item_id == content_id)
            .order_by(PerformanceSnapshot.captured_at.desc())
            .limit(500)
        )
    ).scalars().all()
    return [_json(row) for row in rows]


@router.get("/summary")
async def performance_summary(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = (await db.execute(select(ContentItem).where(ContentItem.project_id == project_id))).scalars().all()
    if not items:
        return {"project_id": str(project_id), "publications": 0, "totals": {}, "by_content_type": {}, "by_rubric": {}}

    item_map = {item.id: item for item in items}
    rows = (
        await db.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.project_id == project_id)
            .order_by(PerformanceSnapshot.captured_at.desc(), PerformanceSnapshot.created_at.desc())
            .limit(20000)
        )
    ).scalars().all()

    latest: dict[tuple[str, str], PerformanceSnapshot] = {}
    for row in rows:
        latest.setdefault((row.source, row.external_publication_id), row)

    runs = (
        await db.execute(select(GenerationRun).where(GenerationRun.content_item_id.in_(list(item_map.keys()))))
    ).scalars().all()
    run_by_content = {run.content_item_id: run for run in runs if run.content_item_id}
    batch_items = []
    if runs:
        batch_items = (
            await db.execute(select(ProductionBatchItem).where(ProductionBatchItem.child_run_id.in_([run.id for run in runs])))
        ).scalars().all()
    batch_item_by_run = {row.child_run_id: row for row in batch_items if row.child_run_id}
    rubric_ids = {row.rubric_id for row in batch_items if row.rubric_id}
    rubrics: dict[uuid.UUID, str] = {}
    if rubric_ids:
        rubric_rows = (await db.execute(select(Rubric).where(Rubric.id.in_(rubric_ids)))).scalars().all()
        rubrics = {row.id: row.name for row in rubric_rows}

    totals: defaultdict[str, float] = defaultdict(float)
    by_type: dict[str, defaultdict[str, float]] = {}
    by_rubric: dict[str, defaultdict[str, float]] = {}
    for snapshot in latest.values():
        item = item_map.get(snapshot.content_item_id)
        if not item:
            continue
        content_type = item.type.value
        type_bucket = by_type.setdefault(content_type, defaultdict(float))
        run = run_by_content.get(item.id)
        batch_item = batch_item_by_run.get(run.id) if run else None
        rubric_name = rubrics.get(batch_item.rubric_id, "Unassigned") if batch_item else "Unassigned"
        rubric_bucket = by_rubric.setdefault(rubric_name, defaultdict(float))
        for metric, raw in (snapshot.metrics or {}).items():
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                value = float(raw)
                totals[metric] += value
                type_bucket[metric] += value
                rubric_bucket[metric] += value

    def clean(bucket: dict[str, float]) -> dict[str, int | float]:
        return {key: int(value) if float(value).is_integer() else round(value, 4) for key, value in bucket.items()}

    return {
        "project_id": str(project_id),
        "publications": len(latest),
        "totals": clean(totals),
        "by_content_type": {key: clean(value) for key, value in by_type.items()},
        "by_rubric": {key: clean(value) for key, value in by_rubric.items()},
    }


@router.get("/learning")
async def performance_learning(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await build_performance_learning_context(db, project_id)


@router.get("/economics")
async def generation_economics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    run_ids = (
        await db.execute(select(GenerationRun.id).where(GenerationRun.project_id == project_id))
    ).scalars().all()
    if not run_ids:
        return {"project_id": str(project_id), **aggregate_generation_economics([])}

    steps = (
        await db.execute(
            select(GenerationStep)
            .where(GenerationStep.run_id.in_(run_ids))
            .order_by(GenerationStep.created_at.desc())
            .limit(50000)
        )
    ).scalars().all()
    records = [
        {"stage": step.stage, "provider": step.provider, "model": step.model, "output_json": step.output_json or {}}
        for step in steps
    ]
    return {"project_id": str(project_id), **aggregate_generation_economics(records)}
