"""Downstream performance ingestion, learning signals and generation economics."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.generation_economics import aggregate_generation_economics
from database.model_router_cache import mark_model_router_snapshot_stale, schedule_model_router_refresh
from database.models import ContentItem, ExportDelivery, GenerationRun, GenerationStep, PerformanceSnapshot, ProductionBatchItem, Project, Rubric, User
from database.performance_learning import SUPPORTED_PRIMARY_METRICS, build_performance_learning_context

from ..access import ensure_project_capability
from ..audit import record_audit
from ..config import config
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.factory import PerformanceIngest
from pydantic import BaseModel, Field

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




class LearningPolicyUpdate(BaseModel):
    primary_metric: str
    exploration_share: float = Field(ge=0.05, le=0.50)
    min_publications: int = Field(ge=5, le=500)


@router.get("/policy")
async def get_learning_policy(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "performance:view")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return {
        "project_id": str(project_id),
        "primary_metric": project.learning_primary_metric,
        "exploration_share": project.learning_exploration_share,
        "min_publications": project.learning_min_publications,
        "supported_metrics": sorted(SUPPORTED_PRIMARY_METRICS),
    }


@router.put("/policy")
async def update_learning_policy(
    project_id: uuid.UUID,
    body: LearningPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "performance:manage")
    metric = body.primary_metric.strip().lower()
    if metric not in SUPPORTED_PRIMARY_METRICS:
        raise HTTPException(400, f"Unsupported primary_metric: {metric}")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    project.learning_primary_metric = metric
    project.learning_exploration_share = float(body.exploration_share)
    project.learning_min_publications = int(body.min_publications)
    await record_audit(db, actor=user, action="learning_policy.update", project_id=project_id, entity_type="project", entity_id=project_id, metadata={"primary_metric": metric, "exploration_share": body.exploration_share, "min_publications": body.min_publications})
    await db.flush()
    return {
        "project_id": str(project_id), "primary_metric": metric,
        "exploration_share": project.learning_exploration_share,
        "min_publications": project.learning_min_publications,
    }


@router.post("/ingest", status_code=202)
async def ingest_performance(
    body: PerformanceIngest,
    x_performance_token: str | None = Header(default=None, alias="X-Performance-Token"),
    db: AsyncSession = Depends(get_db),
):
    _require_ingest_token(x_performance_token)
    if body.source.strip().lower() != "autoposter":
        raise HTTPException(400, "Unsupported performance source")
    try:
        content_id = uuid.UUID(body.content_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid content_id") from exc

    item = await db.scalar(select(ContentItem).where(ContentItem.id == content_id))
    if not item:
        raise HTTPException(404, "Content item not found")
    now = datetime.now(timezone.utc)
    captured_at = body.captured_at if body.captured_at.tzinfo else body.captured_at.replace(tzinfo=timezone.utc)
    if captured_at > now + timedelta(minutes=10):
        raise HTTPException(400, "captured_at cannot be materially in the future")

    existing = await db.scalar(
        select(PerformanceSnapshot).where(
            PerformanceSnapshot.source == body.source,
            PerformanceSnapshot.event_id == body.event_id,
        )
    )
    if existing:
        if existing.content_item_id != content_id or existing.external_publication_id != body.external_publication_id:
            raise HTTPException(409, "event_id was already used for a different publication")
        if existing.metrics != body.metrics or existing.captured_at != captured_at:
            raise HTTPException(409, "event_id was replayed with different performance data")
        return {"status": "duplicate", "snapshot": _json(existing)}

    metadata = body.metadata or {}
    lineage = metadata.get("lineage") if isinstance(metadata.get("lineage"), dict) else {}
    delivery = None
    delivery_id = lineage.get("export_delivery_id")
    if delivery_id:
        try:
            parsed_delivery_id = uuid.UUID(str(delivery_id))
        except ValueError as exc:
            raise HTTPException(400, "Invalid lineage export_delivery_id") from exc
        delivery = await db.scalar(
            select(ExportDelivery).where(
                ExportDelivery.id == parsed_delivery_id,
                ExportDelivery.content_item_id == item.id,
            )
        )
        if delivery is None:
            raise HTTPException(409, "Performance lineage does not match a Factory delivery")
        expected_digest = hashlib.sha256(
            json.dumps(delivery.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        reported_digest = metadata.get("payload_sha256")
        if not reported_digest or not hmac.compare_digest(str(reported_digest), expected_digest):
            raise HTTPException(409, "Performance payload hash does not match the published delivery")
        frozen_lineage = delivery.payload.get("lineage") if isinstance(delivery.payload, dict) else None
        if not isinstance(frozen_lineage, dict) or frozen_lineage != lineage:
            raise HTTPException(409, "Performance lineage differs from the immutable Factory delivery")
        # From here on, trust the Factory-owned delivery copy, never callback-supplied lineage.
        lineage = frozen_lineage
    else:
        parsed_delivery_id = None
        expected_digest = str(metadata.get("payload_sha256") or "") or None

    def lineage_uuid(name: str):
        raw = lineage.get(name)
        if not raw:
            return None
        try:
            return uuid.UUID(str(raw))
        except ValueError as exc:
            raise HTTPException(400, f"Invalid lineage {name}") from exc

    generation_run_id = lineage_uuid("generation_run_id")
    batch_id = lineage_uuid("batch_id")
    rubric_id = lineage_uuid("rubric_id")
    if generation_run_id is not None:
        linked_run = await db.scalar(select(GenerationRun).where(GenerationRun.id == generation_run_id, GenerationRun.content_item_id == item.id))
        if linked_run is None:
            raise HTTPException(409, "Performance generation_run_id does not belong to content item")
    if batch_id is not None:
        batch_link = await db.scalar(
            select(ProductionBatchItem.id).where(
                ProductionBatchItem.batch_id == batch_id,
                ProductionBatchItem.child_run_id == generation_run_id,
            )
        )
        if batch_link is None:
            raise HTTPException(409, "Performance batch_id is not linked to generation run")
    if rubric_id is not None:
        rubric = await db.get(Rubric, rubric_id)
        if rubric is None or rubric.project_id != item.project_id:
            raise HTTPException(409, "Performance rubric_id does not belong to project")

    row = PerformanceSnapshot(
        project_id=item.project_id,
        content_item_id=item.id,
        source=body.source,
        event_id=body.event_id,
        external_publication_id=body.external_publication_id,
        platform=body.platform,
        content_version=int(lineage["content_version"]) if lineage.get("content_version") is not None else None,
        export_delivery_id=parsed_delivery_id,
        payload_sha256=expected_digest,
        generation_run_id=generation_run_id,
        batch_id=batch_id,
        rubric_id=rubric_id,
        prompt_version=str(lineage.get("prompt_version"))[:180] if lineage.get("prompt_version") else None,
        prompt_hash=str(lineage.get("prompt_hash")) if lineage.get("prompt_hash") else None,
        model=str(lineage.get("model"))[:180] if lineage.get("model") else None,
        model_router=lineage.get("model_router") if isinstance(lineage.get("model_router"), dict) else {},
        metrics=body.metrics,
        captured_at=captured_at,
        metadata_json=metadata,
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
    user: User = Depends(get_current_user),
):
    item = await db.get(ContentItem, content_id)
    if item is None:
        raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "performance:view")
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
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "performance:view")
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
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "performance:view")
    return await build_performance_learning_context(db, project_id)


@router.get("/economics")
async def generation_economics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "performance:view")
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
