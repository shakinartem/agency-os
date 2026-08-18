"""Stale-while-revalidate read path for Model Router.

Routing decisions never scan project history synchronously. Raw evidence is aggregated by a
background task into ModelRouterSnapshot. Snapshot compatibility includes default model,
candidate set and prompt cohort, so a prompt-version deployment cannot reuse stale evidence.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .model_router import ROUTED_STAGE_FAMILIES, configured_candidates, router_mode
from .model_router_outcomes import OUTCOME_GATED_STAGE_FAMILIES
from .model_router_prompt import current_content_prompt_version
from .models import ModelRouterSnapshot
from .task_outbox import enqueue_task


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def snapshot_ttl_seconds() -> int:
    return max(30, int(os.getenv("MODEL_ROUTER_SNAPSHOT_TTL_SECONDS", "300")))


def refresh_dedupe_seconds() -> int:
    return max(10, int(os.getenv("MODEL_ROUTER_REFRESH_DEDUPE_SECONDS", "60")))


def _empty_candidate(model: str, default_model: str) -> dict[str, Any]:
    return {
        "model": model,
        "configured": True,
        "samples": 0,
        "quality_samples": 0,
        "performance_samples": 0,
        "priced_samples": 0,
        "live_samples": 0,
        "shadow_samples": 0,
        "average_quality": None,
        "average_performance_proxy": None,
        "average_latency_ms": None,
        "average_cost_usd": None,
        "quality_gate_passed": False,
        "eligible": False,
        "production_eligible": model == default_model,
        "confidence": "low",
        "score": None,
        "requires_downstream_outcomes": False,
        "downstream_gate_passed": model == default_model,
    }


def empty_model_router_report(default_model: str) -> dict[str, Any]:
    candidates = configured_candidates(default_model)
    min_samples = max(3, int(os.getenv("MODEL_ROUTER_MIN_SAMPLES_PER_MODEL", "10")))
    min_live = max(1, int(os.getenv("MODEL_ROUTER_MIN_LIVE_SAMPLES", "3")))
    min_downstream = max(1, int(os.getenv("MODEL_ROUTER_MIN_DOWNSTREAM_SAMPLES", "3")))
    quality_floor = min(1.0, max(0.0, float(os.getenv("MODEL_ROUTER_QUALITY_FLOOR", "0.84"))))
    shadow_rate = min(0.5, max(0.0, float(os.getenv("MODEL_ROUTER_SHADOW_SAMPLE_RATE", "0.05"))))
    explore_rate = min(0.5, max(0.0, float(os.getenv("MODEL_ROUTER_EXPLORATION_RATE", "0.10"))))
    prompt_version = current_content_prompt_version()
    stages: dict[str, Any] = {}
    for family in ROUTED_STAGE_FAMILIES:
        rows = [_empty_candidate(model, default_model) for model in candidates]
        stages[family] = {
            "recommended_model": default_model,
            "shadow_recommended_model": default_model,
            "routing_ready": False,
            "shadow_ready": False,
            "candidate_count": len(rows),
            "eligible_count": 0,
            "production_eligible_count": 1 if default_model in candidates else 0,
            "outcome_gate_required": family in OUTCOME_GATED_STAGE_FAMILIES,
            "candidates": rows,
        }
    return {
        "mode": router_mode(),
        "default_model": default_model,
        "configured_candidates": candidates,
        "evidence_prompt_version": prompt_version,
        "minimum_samples_per_model": min_samples,
        "minimum_live_samples": min_live,
        "minimum_downstream_samples": min_downstream,
        "quality_floor": quality_floor,
        "shadow_sample_rate": shadow_rate,
        "exploration_rate": explore_rate,
        "performance_metric": None,
        "outcome_gated_stages": sorted(OUTCOME_GATED_STAGE_FAMILIES),
        "stages": stages,
        "generated_at": _now().isoformat(),
    }


def _snapshot_config_matches(snapshot: ModelRouterSnapshot | None, default_model: str) -> bool:
    if snapshot is None or snapshot.default_model != default_model:
        return False
    payload = snapshot.payload or {}
    return (
        list(payload.get("configured_candidates") or []) == configured_candidates(default_model)
        and payload.get("evidence_prompt_version") == current_content_prompt_version()
    )


def snapshot_is_fresh(snapshot: ModelRouterSnapshot | None, default_model: str) -> bool:
    if snapshot is None or snapshot.status != "ready" or not _snapshot_config_matches(snapshot, default_model):
        return False
    refreshed_at = _aware(snapshot.refreshed_at)
    if refreshed_at is None:
        return False
    return (_now() - refreshed_at).total_seconds() <= snapshot_ttl_seconds()


async def schedule_model_router_refresh(db: AsyncSession, project_id: uuid.UUID) -> None:
    bucket = int(time.time()) // refresh_dedupe_seconds()
    prompt_version = current_content_prompt_version()
    await enqueue_task(
        db,
        "content_factory.refresh_model_router_snapshot",
        args=[str(project_id)],
        dedupe_key=f"model-router-refresh:{project_id}:{prompt_version}:{bucket}",
    )


async def mark_model_router_snapshot_stale(db: AsyncSession, project_id: uuid.UUID, default_model: str) -> None:
    stmt = insert(ModelRouterSnapshot).values(
        project_id=project_id,
        default_model=default_model,
        status="stale",
        payload={},
    ).on_conflict_do_update(
        index_elements=[ModelRouterSnapshot.project_id],
        set_={"status": "stale", "default_model": default_model},
    )
    await db.execute(stmt)
    await db.flush()


async def store_model_router_snapshot(
    db: AsyncSession,
    project_id: uuid.UUID,
    default_model: str,
    payload: dict[str, Any],
) -> None:
    now = _now()
    stmt = insert(ModelRouterSnapshot).values(
        project_id=project_id,
        default_model=default_model,
        status="ready",
        payload=payload,
        refreshed_at=now,
        error=None,
    ).on_conflict_do_update(
        index_elements=[ModelRouterSnapshot.project_id],
        set_={"default_model": default_model, "status": "ready", "payload": payload, "refreshed_at": now, "error": None},
    )
    await db.execute(stmt)
    await db.flush()


async def store_model_router_refresh_error(
    db: AsyncSession,
    project_id: uuid.UUID,
    default_model: str,
    error: str,
) -> None:
    stmt = insert(ModelRouterSnapshot).values(
        project_id=project_id,
        default_model=default_model,
        status="failed",
        payload={},
        error=error[:4000],
    ).on_conflict_do_update(
        index_elements=[ModelRouterSnapshot.project_id],
        set_={"status": "failed", "default_model": default_model, "error": error[:4000]},
    )
    await db.execute(stmt)
    await db.flush()


async def get_cached_model_router_report(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    default_model: str,
    schedule_refresh: bool = True,
) -> dict[str, Any]:
    snapshot = await db.get(ModelRouterSnapshot, project_id)
    fresh = snapshot_is_fresh(snapshot, default_model)
    config_matches = _snapshot_config_matches(snapshot, default_model)
    if fresh:
        report = dict(snapshot.payload or {})
        state = "ready"
    elif snapshot is not None and snapshot.payload and config_matches:
        report = dict(snapshot.payload)
        state = "stale"
    else:
        report = empty_model_router_report(default_model)
        state = "warming"

    if not fresh and schedule_refresh:
        await schedule_model_router_refresh(db, project_id)

    report["cache"] = {
        "state": state,
        "fresh": fresh,
        "ttl_seconds": snapshot_ttl_seconds(),
        "refreshed_at": _aware(snapshot.refreshed_at).isoformat() if snapshot and snapshot.refreshed_at else None,
        "last_error": snapshot.error if snapshot else None,
        "prompt_version": current_content_prompt_version(),
    }
    return report
