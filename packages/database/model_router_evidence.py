"""Evidence-aware Model Router report.

Shadow trials can establish prompt-level quality/cost/latency evidence, but they cannot prove
real downstream performance. A non-default candidate therefore needs a minimum number of
live production samples before it becomes eligible for full routing. Evidence is isolated by
`CONTENT_PROMPT_VERSION` so prompt changes cannot masquerade as model improvements.
"""
from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from .model_router import (
    ROUTED_STAGE_FAMILIES,
    _performance_scores,
    choose_from_stage_report,
    configured_candidates,
    router_mode,
    score_stage_candidates,
    stage_family,
)
from .model_router_prompt import current_content_prompt_version
from .models import GenerationRun, GenerationStep, PerformanceSnapshot, Project


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _root_provider_meta(output: dict[str, Any]) -> dict[str, Any] | None:
    meta = output.get("_provider_meta")
    return meta if isinstance(meta, dict) else None


def records_from_step(
    step: GenerationStep,
    run: GenerationRun,
    performance_by_run: dict[uuid.UUID, float],
) -> list[dict[str, Any]]:
    """Turn one persisted step into live and optional shadow evidence rows."""
    output = step.output_json or {}
    root_meta = _root_provider_meta(output)
    shadow = output.get("_model_router_shadow")
    if not isinstance(shadow, dict):
        shadow = {}

    live_quality = _number(shadow.get("production_quality"))
    if live_quality is None:
        live_quality = _number(run.quality_score)

    live_model = str((root_meta or {}).get("model") or step.model or "").strip()
    rows: list[dict[str, Any]] = []
    if live_model:
        rows.append({
            "model": live_model,
            "quality": live_quality,
            "performance": performance_by_run.get(run.id),
            "latency_ms": (root_meta or {}).get("latency_ms"),
            "cost_usd": (root_meta or {}).get("estimated_cost_usd"),
            "evidence_source": "live",
        })

    candidate_model = str(shadow.get("candidate_model") or "").strip()
    candidate_meta = shadow.get("candidate_provider_meta")
    candidate_quality = _number(shadow.get("candidate_quality"))
    if candidate_model and isinstance(candidate_meta, dict) and candidate_quality is not None:
        rows.append({
            "model": candidate_model,
            "quality": candidate_quality,
            "performance": None,
            "latency_ms": candidate_meta.get("latency_ms"),
            "cost_usd": candidate_meta.get("estimated_cost_usd"),
            "evidence_source": "shadow",
        })
    return rows


def _score_with_evidence_gates(
    records: list[dict[str, Any]],
    *,
    candidates: list[str],
    default_model: str,
    min_samples: int,
    min_live_samples: int,
    quality_floor: float,
) -> dict[str, Any]:
    report = score_stage_candidates(
        records,
        candidates=candidates,
        default_model=default_model,
        min_samples=min_samples,
        quality_floor=quality_floor,
    )
    live_counts: dict[str, int] = defaultdict(int)
    shadow_counts: dict[str, int] = defaultdict(int)
    for record in records:
        model = str(record.get("model") or "")
        if record.get("evidence_source") == "shadow":
            shadow_counts[model] += 1
        else:
            live_counts[model] += 1

    for row in report["candidates"]:
        model = row["model"]
        row["live_samples"] = live_counts.get(model, 0)
        row["shadow_samples"] = shadow_counts.get(model, 0)
        row["production_eligible"] = bool(
            row["eligible"]
            and (model == default_model or row["live_samples"] >= min_live_samples)
        )

    shadow_ranked = sorted(
        [row for row in report["candidates"] if row.get("eligible") and row.get("score") is not None],
        key=lambda row: (float(row["score"]), int(row["samples"])),
        reverse=True,
    )
    live_ranked = sorted(
        [row for row in report["candidates"] if row.get("production_eligible") and row.get("score") is not None],
        key=lambda row: (float(row["score"]), int(row["live_samples"])),
        reverse=True,
    )
    report["shadow_recommended_model"] = shadow_ranked[0]["model"] if shadow_ranked else default_model
    report["recommended_model"] = live_ranked[0]["model"] if live_ranked else default_model
    report["shadow_ready"] = len(shadow_ranked) >= 2
    report["routing_ready"] = len(live_ranked) >= 2
    report["production_eligible_count"] = len(live_ranked)
    return report


async def build_model_router_report(session, project_id: uuid.UUID, *, default_model: str) -> dict[str, Any]:
    candidates = configured_candidates(default_model)
    min_samples = max(3, int(os.getenv("MODEL_ROUTER_MIN_SAMPLES_PER_MODEL", "10")))
    min_live_samples = max(1, int(os.getenv("MODEL_ROUTER_MIN_LIVE_SAMPLES", "3")))
    quality_floor = min(1.0, max(0.0, float(os.getenv("MODEL_ROUTER_QUALITY_FLOOR", "0.84"))))
    shadow_sample_rate = min(0.5, max(0.0, float(os.getenv("MODEL_ROUTER_SHADOW_SAMPLE_RATE", "0.05"))))
    exploration_rate = min(0.5, max(0.0, float(os.getenv("MODEL_ROUTER_EXPLORATION_RATE", "0.10"))))
    prompt_version = current_content_prompt_version()

    runs = (await session.execute(select(GenerationRun).where(GenerationRun.project_id == project_id))).scalars().all()
    run_map = {run.id: run for run in runs}
    project = await session.get(Project, project_id)
    configured_metric = getattr(project, "learning_primary_metric", None) if project else None

    performance_metric = None
    performance_by_run: dict[uuid.UUID, float] = {}
    run_ids = set(run_map)
    if run_ids:
        # Only exact 1.1 publication lineage may influence model routing. Legacy content-level
        # analytics remain visible in reporting but are not causal enough to promote a model.
        raw = (await session.execute(
            select(PerformanceSnapshot)
            .where(
                PerformanceSnapshot.project_id == project_id,
                PerformanceSnapshot.generation_run_id.in_(list(run_ids)),
                PerformanceSnapshot.payload_sha256.is_not(None),
            )
            .order_by(PerformanceSnapshot.captured_at.desc(), PerformanceSnapshot.created_at.desc())
            .limit(20000)
        )).scalars().all()
        latest: dict[tuple[str, str], PerformanceSnapshot] = {}
        for snapshot in raw:
            latest.setdefault((snapshot.source, snapshot.external_publication_id), snapshot)
        if latest:
            # Reuse metric normalization by treating a generation run as the attribution unit.
            performance_metric, raw_scores = _performance_scores([
                {"content_item_id": row.generation_run_id, "metrics": row.metrics or {}}
                for row in latest.values()
                if row.generation_run_id is not None
            ], metric_override=configured_metric)
            performance_by_run = raw_scores

    records_by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if run_map:
        steps = (await session.execute(
            select(GenerationStep)
            .where(
                GenerationStep.run_id.in_(list(run_map)),
                GenerationStep.provider == "openai-compatible",
                GenerationStep.prompt_version == prompt_version,
            )
            .order_by(GenerationStep.created_at.desc())
            .limit(50000)
        )).scalars().all()
        for step in steps:
            family = stage_family(step.stage)
            run = run_map.get(step.run_id)
            if family is None or run is None:
                continue
            records_by_stage[family].extend(records_from_step(step, run, performance_by_run))

    stages = {
        family: _score_with_evidence_gates(
            records_by_stage.get(family, []),
            candidates=candidates,
            default_model=default_model,
            min_samples=min_samples,
            min_live_samples=min_live_samples,
            quality_floor=quality_floor,
        )
        for family in ROUTED_STAGE_FAMILIES
    }
    return {
        "mode": router_mode(),
        "default_model": default_model,
        "configured_candidates": candidates,
        "evidence_prompt_version": prompt_version,
        "minimum_samples_per_model": min_samples,
        "minimum_live_samples": min_live_samples,
        "quality_floor": quality_floor,
        "shadow_sample_rate": shadow_sample_rate,
        "exploration_rate": exploration_rate,
        "performance_metric": performance_metric,
        "stages": stages,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def choose_model_for_run_stage(session, run: GenerationRun, stage: str, *, default_model: str) -> dict[str, Any]:
    family = stage_family(stage)
    mode = router_mode()
    if family is None or mode == "off":
        return choose_from_stage_report(
            {},
            run_id=run.id,
            stage=stage,
            default_model=default_model,
            mode=mode,
            exploration_rate=0.0,
        )

    options = dict(run.options or {})
    decisions = dict(options.get("_model_router_decisions") or {})
    existing = decisions.get(family)
    if isinstance(existing, dict) and existing.get("selected_model"):
        return existing

    report = options.get("_model_router_report")
    if not isinstance(report, dict) or report.get("default_model") != default_model:
        report = await build_model_router_report(session, run.project_id, default_model=default_model)
        options["_model_router_report"] = report

    stage_report = dict((report.get("stages") or {}).get(family) or {})
    if mode == "shadow":
        stage_report["recommended_model"] = stage_report.get("shadow_recommended_model") or default_model

    decision = choose_from_stage_report(
        stage_report,
        run_id=run.id,
        stage=stage,
        default_model=default_model,
        mode=mode,
        exploration_rate=float(report.get("exploration_rate") or 0.0),
    )
    decision["shadow_sample_rate"] = float(report.get("shadow_sample_rate") or 0.0)
    decision["evidence"] = {
        "prompt_version": report.get("evidence_prompt_version"),
        "minimum_samples_per_model": report.get("minimum_samples_per_model"),
        "minimum_live_samples": report.get("minimum_live_samples"),
        "quality_floor": report.get("quality_floor"),
        "performance_metric": report.get("performance_metric"),
        "candidates": stage_report.get("candidates") or [],
    }
    decisions[family] = decision
    options["_model_router_decisions"] = decisions
    run.options = options
    await session.flush()
    return decision
