"""Content Factory orchestration API."""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import ContentStatus, GenerationRunStatus, GenerationStepStatus, UserRole
from database.models import (
    BrandProfile,
    ContentItem,
    ContentVariant,
    ContentVersion,
    Evaluation,
    ExportDelivery,
    GenerationRun,
    GenerationStep,
    MediaAsset,
    ProductionBatch,
    ProductionBatchItem,
    Project,
    ReviewDecision,
    Rubric,
    TaskOutbox,
    User,
)

from ..access import accessible_project_ids, ensure_project_capability
from ..audit import record_audit
from ..config import config
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.factory import BatchCreate, BrandProfileUpsert, ReviewDecisionPayload, RubricCreate, RunCreate
from ..services.task_outbox import enqueue_task, nudge_dispatcher

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


async def _record_review(db: AsyncSession, *, item: ContentItem, user: User, action: str, body: ReviewDecisionPayload | None) -> ReviewDecision:
    if body and body.action and body.action != action:
        raise HTTPException(400, f"This endpoint records action={action}, not {body.action}")
    row = ReviewDecision(
        content_item_id=item.id,
        user_id=user.id,
        content_version=item.current_version,
        action=action,
        reason_codes=(body.reason_codes if body else []),
        note=(body.note if body else None),
        metadata_json=(body.metadata if body else {}),
    )
    db.add(row)
    await db.flush()
    return row


@router.get("/capabilities")
async def capabilities(_: User = Depends(get_current_user)):
    return {
        "llm": os.getenv("FACTORY_LLM_ENABLED", "false").lower() in {"1", "true", "yes", "on"} or bool(config.llm_api_key),
        "research": os.getenv("FACTORY_RESEARCH_ENABLED", "false").lower() in {"1", "true", "yes", "on"} or bool(os.getenv("TAVILY_API_KEY")),
        "image_generation": os.getenv("FACTORY_IMAGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"} or bool(config.image_api_key or config.llm_api_key),
        "object_storage": os.getenv("FACTORY_OBJECT_STORAGE_ENABLED", "false").lower() in {"1", "true", "yes", "on"} or all(bool(os.getenv(name)) for name in ("S3_ENDPOINT_URL", "S3_ACCESS_KEY", "S3_SECRET_KEY")),
        "autoposter": bool(config.autoposter_url),
        "performance_ingest": bool(config.performance_ingest_token),
        "transactional_task_outbox": True,
    }


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")
    await ensure_project_capability(db, user, project_id, "content:generate")

    options = {
        **body.options,
        "use_research": body.use_research,
        "use_knowledge": body.use_knowledge,
        "generate_media": body.generate_media,
        "auto_export": body.auto_export,
    }
    run = GenerationRun(project_id=project_id, task=body.task, content_type=body.content_type, platforms=body.platforms, options=options)
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await enqueue_task(db, "content_factory.process_run", args=[str(run.id)], dedupe_key=f"run:{run.id}:process")
    await record_audit(db, actor=user, action="content.run.create", project_id=project_id, entity_type="generation_run", entity_id=run.id, metadata={"content_type": body.content_type, "platforms": body.platforms})
    response = _json(run)
    await db.commit()
    nudge_dispatcher(queue)
    return response


@router.get("/runs")
async def list_runs(project_id: str | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(GenerationRun).order_by(GenerationRun.created_at.desc()).limit(200)
    if project_id:
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid project_id") from exc
        await ensure_project_capability(db, user, parsed_project_id, "content:read")
        stmt = stmt.where(GenerationRun.project_id == parsed_project_id)
    else:
        ids = await accessible_project_ids(db, user)
        if ids is not None:
            if not ids:
                return []
            stmt = stmt.where(GenerationRun.project_id.in_(ids))
    return [_json(row) for row in (await db.execute(stmt)).scalars().all()]


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    run = await db.scalar(select(GenerationRun).where(GenerationRun.id == run_id))
    if not run:
        raise HTTPException(404, "Generation run not found")
    await ensure_project_capability(db, user, run.project_id, "content:read")
    return _json(run)


@router.post("/batches", status_code=status.HTTP_202_ACCEPTED)
async def create_batch(body: BatchCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")
    await ensure_project_capability(db, user, project_id, "content:generate")

    options = {
        **body.options,
        "use_research": body.use_research,
        "use_knowledge": body.use_knowledge,
        "generate_media": body.generate_media,
        "auto_export": body.auto_export,
    }
    planner_run = GenerationRun(
        project_id=project_id,
        task=f"Plan a production batch. Objective: {body.objective}",
        content_type="batch_plan",
        platforms=body.platforms,
        options={**options, "content_mix": body.content_mix},
    )
    db.add(planner_run)
    await db.flush()
    batch = ProductionBatch(
        project_id=project_id,
        planner_run_id=planner_run.id,
        objective=body.objective,
        platforms=body.platforms,
        content_mix=body.content_mix,
        options=options,
        status="queued",
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)
    await enqueue_task(db, "content_factory.plan_batch", args=[str(batch.id)], dedupe_key=f"batch:{batch.id}:plan")
    response = _json(batch)
    await db.commit()
    nudge_dispatcher(queue)
    return response


@router.get("/batches")
async def list_batches(project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ProductionBatch).order_by(ProductionBatch.created_at.desc()).limit(200)
    if project_id:
        await ensure_project_capability(db, user, project_id, "content:read")
        stmt = stmt.where(ProductionBatch.project_id == project_id)
    else:
        ids = await accessible_project_ids(db, user)
        if ids is not None:
            if not ids:
                return []
            stmt = stmt.where(ProductionBatch.project_id.in_(ids))
    return [_json(row) for row in (await db.execute(stmt)).scalars().all()]


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    batch = await db.scalar(select(ProductionBatch).where(ProductionBatch.id == batch_id))
    if not batch:
        raise HTTPException(404, "Production batch not found")
    await ensure_project_capability(db, user, batch.project_id, "content:read")
    items = (await db.execute(select(ProductionBatchItem).where(ProductionBatchItem.batch_id == batch_id).order_by(ProductionBatchItem.position.asc()))).scalars().all()
    run_ids = [row.child_run_id for row in items if row.child_run_id]
    run_map: dict[uuid.UUID, GenerationRun] = {}
    if run_ids:
        runs = (await db.execute(select(GenerationRun).where(GenerationRun.id.in_(run_ids)))).scalars().all()
        run_map = {run.id: run for run in runs}
    payloads, counts = [], {}
    for row in items:
        payload = _json(row)
        run = run_map.get(row.child_run_id) if row.child_run_id else None
        effective_status = run.status.value if run else row.status
        payload["run_status"] = effective_status
        payload["content_item_id"] = str(run.content_item_id) if run and run.content_item_id else None
        payload["quality_score"] = run.quality_score if run else None
        counts[effective_status] = counts.get(effective_status, 0) + 1
        payloads.append(payload)
    return {"batch": _json(batch), "counts": counts, "items": payloads}


@router.get("/content/{content_id}/detail")
async def content_detail(content_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == content_id))
    if not item:
        raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:read")
    versions = (await db.execute(select(ContentVersion).where(ContentVersion.content_item_id == content_id).order_by(ContentVersion.version.desc()))).scalars().all()
    evaluations = (await db.execute(select(Evaluation).where(Evaluation.content_item_id == content_id).order_by(Evaluation.created_at.desc()))).scalars().all()
    variants = (await db.execute(select(ContentVariant).where(ContentVariant.content_item_id == content_id).order_by(ContentVariant.platform.asc()))).scalars().all()
    media = (await db.execute(select(MediaAsset).where(MediaAsset.content_item_id == content_id).order_by(MediaAsset.created_at.desc()))).scalars().all()
    runs = (await db.execute(select(GenerationRun).where(GenerationRun.content_item_id == content_id).order_by(GenerationRun.created_at.desc()))).scalars().all()
    decisions = (await db.execute(select(ReviewDecision).where(ReviewDecision.content_item_id == content_id).order_by(ReviewDecision.created_at.desc()))).scalars().all()
    return {
        "content": _json(item),
        "versions": [_json(row) for row in versions],
        "evaluations": [_json(row) for row in evaluations],
        "variants": [_json(row) for row in variants],
        "media": [_json(row) for row in media],
        "runs": [_json(row) for row in runs],
        "review_decisions": [_json(row) for row in decisions],
    }


@router.post("/content/{content_id}/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_content(content_id: uuid.UUID, body: ReviewDecisionPayload | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == content_id))
    if not item:
        raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:approve")
    if item.status == ContentStatus.archived:
        raise HTTPException(409, "Archived content cannot be approved")
    await _record_review(db, item=item, user=user, action="approve", body=body)
    run = await db.scalar(select(GenerationRun).where(GenerationRun.content_item_id == content_id).order_by(GenerationRun.created_at.desc()))
    if run:
        run.status = GenerationRunStatus.running
        run.current_stage = "human_approved"
        db.add(GenerationStep(
            run_id=run.id,
            stage="human_approve",
            status=GenerationStepStatus.passed,
            provider="human",
            model=None,
            prompt_version="manual-v2",
            input_json={"user_id": str(user.id), "reason_codes": body.reason_codes if body else [], "note": body.note if body else None},
            output_json={"approved": True},
        ))
    item.status = ContentStatus.adapting
    await enqueue_task(db, "content_factory.approve_content", args=[str(item.id)], dedupe_key=f"content:{item.id}:approve:v{item.current_version}")
    await record_audit(db, actor=user, action="content.approve", project_id=item.project_id, entity_type="content_item", entity_id=item.id, metadata={"content_version": item.current_version, "reason_codes": body.reason_codes if body else []})
    await db.commit()
    nudge_dispatcher(queue)
    return {"id": str(item.id), "status": "approved_for_downstream_processing"}


@router.post("/content/{content_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_content(content_id: uuid.UUID, body: ReviewDecisionPayload | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.scalar(select(ContentItem).where(ContentItem.id == content_id))
    if not item:
        raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, item.project_id, "content:generate")
    await _record_review(db, item=item, user=user, action="regenerate", body=body)
    latest_run = await db.scalar(select(GenerationRun).where(GenerationRun.content_item_id == content_id).order_by(GenerationRun.created_at.desc()))
    options = dict(latest_run.options or {}) if latest_run else {"use_research": True, "use_knowledge": True, "generate_media": True, "auto_export": False}
    options["regenerated_from_content_id"] = str(content_id)
    run = GenerationRun(project_id=item.project_id, task=item.task or item.topic or item.title, content_type=item.type.value, platforms=item.platforms or ["telegram"], options=options)
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await enqueue_task(db, "content_factory.process_run", args=[str(run.id)], dedupe_key=f"run:{run.id}:process")
    response = _json(run)
    await record_audit(db, actor=user, action="content.regenerate", project_id=item.project_id, entity_type="generation_run", entity_id=run.id, metadata={"source_content_id": str(item.id), "source_version": item.current_version})
    await db.commit()
    nudge_dispatcher(queue)
    return response


@router.get("/brand/{project_id}")
async def get_brand_profile(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "brand:read")
    row = await db.scalar(select(BrandProfile).where(BrandProfile.project_id == project_id))
    return _json(row) if row else None


@router.put("/brand/{project_id}")
async def upsert_brand_profile(project_id: uuid.UUID, body: BrandProfileUpsert, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(404, "Project not found")
    await ensure_project_capability(db, user, project_id, "brand:write")
    row = await db.scalar(select(BrandProfile).where(BrandProfile.project_id == project_id))
    if row is None:
        row = BrandProfile(project_id=project_id, **body.model_dump())
        db.add(row)
    else:
        for key, value in body.model_dump().items():
            setattr(row, key, value)
    await record_audit(db, actor=user, action="brand.update", project_id=project_id, entity_type="brand_profile", entity_id=row.id, metadata={"fields": sorted(body.model_dump())})
    await db.flush()
    await db.refresh(row)
    return _json(row)


@router.get("/rubrics")
async def list_rubrics(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await ensure_project_capability(db, user, project_id, "rubric:read")
    rows = (await db.execute(select(Rubric).where(Rubric.project_id == project_id, Rubric.active.is_(True)).order_by(Rubric.created_at.desc()))).scalars().all()
    return [_json(row) for row in rows]


@router.post("/rubrics", status_code=status.HTTP_201_CREATED)
async def create_rubric(body: RubricCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        project_id = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid project_id") from exc
    if not await db.scalar(select(Project.id).where(Project.id == project_id)):
        raise HTTPException(404, "Project not found")
    await ensure_project_capability(db, user, project_id, "rubric:write")
    row = Rubric(project_id=project_id, name=body.name, description=body.description, goal=body.goal, content_types=body.content_types, platforms=body.platforms)
    db.add(row)
    await db.flush()
    await record_audit(db, actor=user, action="rubric.create", project_id=project_id, entity_type="rubric", entity_id=row.id, metadata={"name": row.name})
    await db.refresh(row)
    return _json(row)


@router.get("/outbox")
async def list_outbox(project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ExportDelivery).order_by(ExportDelivery.created_at.desc()).limit(200)
    if project_id:
        await ensure_project_capability(db, user, project_id, "content:read")
        stmt = stmt.join(ContentItem, ContentItem.id == ExportDelivery.content_item_id).where(ContentItem.project_id == project_id)
    else:
        ids = await accessible_project_ids(db, user)
        if ids is not None:
            if not ids:
                return []
            stmt = stmt.join(ContentItem, ContentItem.id == ExportDelivery.content_item_id).where(ContentItem.project_id.in_(ids))
    return [_json(row) for row in (await db.execute(stmt)).scalars().all()]


@router.post("/outbox/{delivery_id}/send", status_code=status.HTTP_202_ACCEPTED)
async def send_outbox_delivery(delivery_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    delivery = await db.scalar(select(ExportDelivery).where(ExportDelivery.id == delivery_id))
    if not delivery:
        raise HTTPException(404, "Export delivery not found")
    source_item = await db.get(ContentItem, delivery.content_item_id)
    if source_item is None:
        raise HTTPException(404, "Content item not found")
    await ensure_project_capability(db, user, source_item.project_id, "content:publish")
    if delivery.payload.get("status") != "approved":
        raise HTTPException(409, "Only approved content packages can be sent to Autoposter")
    await enqueue_task(db, "content_factory.send_delivery_v2", args=[str(delivery.id)], dedupe_key=f"delivery:{delivery.id}:send")
    await record_audit(db, actor=user, action="delivery.send", project_id=source_item.project_id, entity_type="export_delivery", entity_id=delivery.id, metadata={"content_item_id": str(source_item.id), "schema_version": delivery.schema_version})
    await db.commit()
    nudge_dispatcher(queue)
    return {"id": str(delivery.id), "status": "queued_for_delivery"}


SAFE_OUTBOX_RETRY_TASKS = {
    "content_factory.send_delivery_v2",
    "content_factory.refresh_model_router_snapshot",
}


@router.get("/operations/task-outbox")
async def operations_task_outbox(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    stmt = select(TaskOutbox).order_by(TaskOutbox.created_at.desc()).limit(500)
    if status_filter:
        stmt = stmt.where(TaskOutbox.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return [_json(row) for row in rows]


@router.post("/operations/task-outbox/{outbox_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_safe_outbox_task(
    outbox_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin)),
):
    row = await db.get(TaskOutbox, outbox_id)
    if row is None:
        raise HTTPException(404, "Task outbox row not found")
    if row.task_name not in SAFE_OUTBOX_RETRY_TASKS:
        raise HTTPException(409, "This task is not safe for blind retry; use run recovery instead")
    if row.status == "completed":
        return {"id": str(row.id), "status": "completed", "detail": "Task already completed"}
    row.status = "pending"
    row.available_at = datetime.now(timezone.utc)
    row.last_error = None
    await record_audit(db, actor=user, action="operations.outbox.retry", entity_type="task_outbox", entity_id=row.id, metadata={"task_name": row.task_name})
    await db.commit()
    nudge_dispatcher(queue)
    return {"id": str(row.id), "status": "queued_for_retry", "task_name": row.task_name}


@router.post("/operations/runs/{run_id}/recover", status_code=status.HTTP_202_ACCEPTED)
async def recover_generation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin)),
):
    source = await db.get(GenerationRun, run_id)
    if source is None:
        raise HTTPException(404, "Generation run not found")
    if source.status == GenerationRunStatus.completed:
        raise HTTPException(409, "Completed generation runs do not need recovery")
    options = dict(source.options or {})
    options["recovery_of_run_id"] = str(source.id)
    options["recovery_reason"] = "operator_recovery"
    recovered = GenerationRun(
        project_id=source.project_id,
        task=source.task,
        content_type=source.content_type,
        platforms=list(source.platforms or []),
        options=options,
    )
    db.add(recovered)
    await db.flush()
    await enqueue_task(
        db,
        "content_factory.process_run",
        args=[str(recovered.id)],
        dedupe_key=f"run:{recovered.id}:process",
    )
    await record_audit(db, actor=user, action="operations.run.recover", project_id=source.project_id, entity_type="generation_run", entity_id=recovered.id, metadata={"recovery_of_run_id": str(source.id)})
    await db.commit()
    nudge_dispatcher(queue)
    return {
        "id": str(recovered.id),
        "status": "queued_for_recovery",
        "recovery_of_run_id": str(source.id),
    }
