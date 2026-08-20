"""Cached Model Router diagnostics plus isolated Prompt × Model experiment registry."""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.model_router import ROUTED_STAGE_FAMILIES, configured_candidates
from database.model_router_cache import get_cached_model_router_report
from database.model_router_prompt import current_content_prompt_version
from database.models import (
    Project,
    PromptExperiment,
    PromptExperimentArm,
    User,
)
from database.prompt_experiments import MAX_SHADOW_SAMPLE_RATE, build_prompt_experiment_report

from ..access import ensure_project_capability
from ..audit import record_audit
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/model-routing", tags=["model-routing"])


class ExperimentArmCreate(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    model: str | None = Field(default=None, max_length=180)
    system_append: str | None = Field(default=None, max_length=8000)
    prompt_append: str | None = Field(default=None, max_length=8000)


class PromptExperimentCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    hypothesis: str | None = Field(default=None, max_length=4000)
    stage_family: str
    content_types: list[str] = Field(default_factory=list)
    sample_rate: float = Field(default=0.05, ge=0.01, le=MAX_SHADOW_SAMPLE_RATE)
    min_samples: int = Field(default=20, ge=5, le=500)
    arms: list[ExperimentArmCreate]


def _default_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-5.6")


def _validate_arm_key(value: str) -> str:
    key = value.strip().lower().replace(" ", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", key):
        raise HTTPException(400, "arm.key must match [a-z0-9][a-z0-9_-]*")
    return key


def _experiment_json(row: PromptExperiment) -> dict:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "stage_family": row.stage_family,
        "status": row.status,
        "sample_rate": row.sample_rate,
        "min_samples": row.min_samples,
        "control_prompt_version": row.control_prompt_version,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


@router.get("/report")
async def model_routing_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "router:view")
    report = await get_cached_model_router_report(
        db,
        project_id,
        default_model=_default_model(),
        schedule_refresh=True,
    )
    return {"project_id": str(project_id), **report}


@router.get("/experiments")
async def prompt_experiments_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, project_id, "experiments:view")
    return await build_prompt_experiment_report(db, project_id)


@router.post("/experiments", status_code=201)
async def create_prompt_experiment(
    body: PromptExperimentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ensure_project_capability(db, user, body.project_id, "experiments:manage")
    if body.stage_family not in ROUTED_STAGE_FAMILIES:
        raise HTTPException(400, f"Unsupported stage_family: {body.stage_family}")
    if not 1 <= len(body.arms) <= 4:
        raise HTTPException(400, "Experiment must have 1..4 candidate arms")
    if len(body.content_types) > 20:
        raise HTTPException(400, "content_types is too large")

    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    default_model = _default_model()
    allowed_models = set(configured_candidates(default_model))
    normalized_keys: list[str] = []
    prepared_arms: list[tuple[ExperimentArmCreate, str]] = []
    for arm in body.arms:
        key = _validate_arm_key(arm.key)
        if key in normalized_keys:
            raise HTTPException(400, f"Duplicate arm key: {key}")
        normalized_keys.append(key)
        model = (arm.model or "").strip() or None
        if model is not None and model not in allowed_models:
            raise HTTPException(400, f"Arm model is not in LLM_MODEL_CANDIDATES: {model}")
        has_prompt_delta = bool((arm.system_append or "").strip() or (arm.prompt_append or "").strip())
        has_model_delta = model is not None and model != default_model
        if not has_prompt_delta and not has_model_delta:
            raise HTTPException(400, f"Arm {key} does not change prompt or model")
        prepared_arms.append((arm, key))

    experiment = PromptExperiment(
        project_id=body.project_id,
        created_by_user_id=user.id,
        name=body.name.strip(),
        hypothesis=(body.hypothesis or "").strip() or None,
        stage_family=body.stage_family,
        content_types=sorted(set(value.strip() for value in body.content_types if value.strip())),
        status="draft",
        sample_rate=float(body.sample_rate),
        min_samples=int(body.min_samples),
        primary_metric="judge_quality",
        control_prompt_version=current_content_prompt_version(),
        metadata_json={"auto_promotion": False},
    )
    db.add(experiment)
    await db.flush()
    for arm, key in prepared_arms:
        db.add(PromptExperimentArm(
            experiment_id=experiment.id,
            key=key,
            name=arm.name.strip(),
            model=(arm.model or "").strip() or None,
            system_append=(arm.system_append or "").strip() or None,
            prompt_append=(arm.prompt_append or "").strip() or None,
            active=True,
            metadata_json={},
        ))
    await record_audit(db, actor=user, action="experiment.create", project_id=body.project_id, entity_type="experiment", entity_id=experiment.id, metadata={"stage_family": body.stage_family, "sample_rate": body.sample_rate})
    await db.commit()
    await db.refresh(experiment)
    return _experiment_json(experiment)


async def _get_experiment(db: AsyncSession, experiment_id: uuid.UUID) -> PromptExperiment:
    row = await db.get(PromptExperiment, experiment_id)
    if row is None:
        raise HTTPException(404, "Experiment not found")
    return row


@router.post("/experiments/{experiment_id}/start")
async def start_prompt_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_capability(db, user, experiment.project_id, "experiments:manage")
    if experiment.status not in {"draft", "paused"}:
        raise HTTPException(409, f"Cannot start experiment from status {experiment.status}")
    if experiment.control_prompt_version != current_content_prompt_version():
        raise HTTPException(
            409,
            "Prompt cohort changed after experiment creation. Create a new experiment instead of mixing cohorts.",
        )

    active = await db.scalar(
        select(PromptExperiment.id).where(
            PromptExperiment.project_id == experiment.project_id,
            PromptExperiment.stage_family == experiment.stage_family,
            PromptExperiment.status == "shadow",
            PromptExperiment.id != experiment.id,
        )
    )
    if active is not None:
        raise HTTPException(409, "Another shadow experiment is already active for this project/stage")

    experiment.status = "shadow"
    experiment.started_at = experiment.started_at or datetime.now(timezone.utc)
    experiment.completed_at = None
    await record_audit(db, actor=user, action="experiment.start", project_id=experiment.project_id, entity_type="experiment", entity_id=experiment.id)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Another shadow experiment became active for this project/stage") from exc
    return _experiment_json(experiment)


@router.post("/experiments/{experiment_id}/pause")
async def pause_prompt_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_capability(db, user, experiment.project_id, "experiments:manage")
    if experiment.status != "shadow":
        raise HTTPException(409, "Only a shadow experiment can be paused")
    experiment.status = "paused"
    await record_audit(db, actor=user, action="experiment.pause", project_id=experiment.project_id, entity_type="experiment", entity_id=experiment.id)
    await db.commit()
    return _experiment_json(experiment)


@router.post("/experiments/{experiment_id}/complete")
async def complete_prompt_experiment(
    experiment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    experiment = await _get_experiment(db, experiment_id)
    await ensure_project_capability(db, user, experiment.project_id, "experiments:manage")
    if experiment.status not in {"shadow", "paused"}:
        raise HTTPException(409, "Only shadow/paused experiments can be completed")
    experiment.status = "completed"
    experiment.completed_at = datetime.now(timezone.utc)
    await record_audit(db, actor=user, action="experiment.complete", project_id=experiment.project_id, entity_type="experiment", entity_id=experiment.id)
    await db.commit()
    return _experiment_json(experiment)
