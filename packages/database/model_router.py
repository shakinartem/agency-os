"""Conservative, auditable model routing for Content Factory text stages.

The router treats historical quality and downstream performance as noisy evidence, not
causal truth. A model must clear sample-size and quality gates before cost/latency can
make it an active routing winner. Shadow mode is the default so recommendations can be
observed before they are allowed to change production traffic.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select

from .generation_economics import extract_provider_meta
from .models import GenerationRun, GenerationStep, PerformanceSnapshot

ROUTED_STAGE_FAMILIES = (
    "draft",
    "evaluate",
    "revise",
    "humanize",
    "adapt",
    "batch_plan",
    "strategy_write",
    "strategy_review",
)


def router_mode() -> str:
    value = os.getenv("MODEL_ROUTER_MODE", "shadow").strip().lower()
    return value if value in {"off", "shadow", "active"} else "shadow"


def configured_candidates(default_model: str) -> list[str]:
    raw = os.getenv("LLM_MODEL_CANDIDATES", "")
    values = [part.strip() for part in raw.split(",") if part.strip()]
    result: list[str] = []
    for model in [default_model, *values]:
        if model and model not in result:
            result.append(model)
    return result


def stage_family(stage: str) -> str | None:
    value = (stage or "").strip().lower()
    if value == "draft":
        return "draft"
    if value in {"evaluate", "final_evaluate"}:
        return "evaluate"
    if value == "revise":
        return "revise"
    if value == "humanize":
        return "humanize"
    if value.startswith("adapt:"):
        return "adapt"
    if value in {"batch_generate_plan", "batch_revise_plan"}:
        return "batch_plan"
    if value in {"rubric_generate", "rubric_revise"}:
        return "strategy_write"
    if value in {"rubric_critic", "rubric_recheck"}:
        return "strategy_review"
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return sum(rows) / len(rows) if rows else None


def _confidence(samples: int, minimum: int) -> str:
    if samples >= max(minimum * 3, 30):
        return "high"
    if samples >= minimum:
        return "medium"
    return "low"


def _metric_bucket() -> dict[str, float]:
    return {"reach": 0.0, "clicks": 0.0, "leads": 0.0, "conversions": 0.0, "publications": 0.0}


def _add_metrics(bucket: dict[str, float], metrics: dict[str, Any]) -> None:
    bucket["publications"] += 1
    views = _number(metrics.get("views"))
    impressions = _number(metrics.get("impressions"))
    bucket["reach"] += views if views is not None else (impressions or 0.0)
    for key in ("clicks", "leads", "conversions"):
        bucket[key] += _number(metrics.get(key)) or 0.0


def _primary_metric(bucket: dict[str, float]) -> str:
    if bucket["conversions"] > 0 and bucket["reach"] > 0:
        return "conversions_per_1000_views"
    if bucket["leads"] > 0 and bucket["reach"] > 0:
        return "leads_per_1000_views"
    if bucket["clicks"] > 0 and bucket["reach"] > 0:
        return "ctr"
    return "views_per_publication"


def _metric_value(bucket: dict[str, float], metric: str) -> float:
    reach = bucket["reach"]
    if metric == "conversions_per_1000_views":
        return bucket["conversions"] / reach * 1000 if reach > 0 else 0.0
    if metric == "leads_per_1000_views":
        return bucket["leads"] / reach * 1000 if reach > 0 else 0.0
    if metric == "ctr":
        return bucket["clicks"] / reach if reach > 0 else 0.0
    return reach / bucket["publications"] if bucket["publications"] > 0 else 0.0


def _performance_scores(records: list[dict[str, Any]]) -> tuple[str, dict[uuid.UUID, float]]:
    total = _metric_bucket()
    by_content: dict[uuid.UUID, dict[str, float]] = defaultdict(_metric_bucket)
    for row in records:
        content_id = row.get("content_item_id")
        if not isinstance(content_id, uuid.UUID):
            continue
        metrics = row.get("metrics") or {}
        _add_metrics(total, metrics)
        _add_metrics(by_content[content_id], metrics)
    metric = _primary_metric(total)
    baseline = _metric_value(total, metric)
    if baseline <= 0:
        return metric, {}
    scores = {
        content_id: max(0.0, min(1.0, (_metric_value(bucket, metric) / baseline) / 2.0))
        for content_id, bucket in by_content.items()
    }
    return metric, scores


def score_stage_candidates(
    records: list[dict[str, Any]],
    *,
    candidates: list[str],
    default_model: str,
    min_samples: int,
    quality_floor: float,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        model = str(row.get("model") or "").strip()
        if model:
            grouped[model].append(row)

    candidate_rows: list[dict[str, Any]] = []
    for model in candidates:
        rows = grouped.get(model, [])
        quality_values = [v for row in rows if (v := _number(row.get("quality"))) is not None]
        performance_values = [v for row in rows if (v := _number(row.get("performance"))) is not None]
        latency_values = [v for row in rows if (v := _number(row.get("latency_ms"))) is not None]
        cost_values = [v for row in rows if (v := _number(row.get("cost_usd"))) is not None]
        quality = _mean(quality_values)
        performance = _mean(performance_values)
        latency = _mean(latency_values)
        cost = _mean(cost_values)
        samples = len(rows)
        quality_gate = quality is not None and quality >= quality_floor
        eligible = samples >= min_samples and len(quality_values) >= max(3, min_samples // 2) and quality_gate
        candidate_rows.append({
            "model": model,
            "configured": True,
            "samples": samples,
            "quality_samples": len(quality_values),
            "performance_samples": len(performance_values),
            "priced_samples": len(cost_values),
            "average_quality": round(quality, 4) if quality is not None else None,
            "average_performance_proxy": round(performance, 4) if performance is not None else None,
            "average_latency_ms": round(latency) if latency is not None else None,
            "average_cost_usd": round(cost, 8) if cost is not None else None,
            "quality_gate_passed": quality_gate,
            "eligible": eligible,
            "confidence": _confidence(samples, min_samples),
        })

    eligible_rows = [row for row in candidate_rows if row["eligible"]]
    min_latency = min((row["average_latency_ms"] for row in eligible_rows if row["average_latency_ms"] and row["average_latency_ms"] > 0), default=None)
    min_cost = min((row["average_cost_usd"] for row in eligible_rows if row["average_cost_usd"] is not None and row["average_cost_usd"] > 0), default=None)

    weights = {
        "quality": float(os.getenv("MODEL_ROUTER_QUALITY_WEIGHT", "0.65")),
        "performance": float(os.getenv("MODEL_ROUTER_PERFORMANCE_WEIGHT", "0.20")),
        "latency": float(os.getenv("MODEL_ROUTER_LATENCY_WEIGHT", "0.10")),
        "cost": float(os.getenv("MODEL_ROUTER_COST_WEIGHT", "0.05")),
    }
    for row in candidate_rows:
        if not row["eligible"]:
            row["score"] = None
            continue
        components: list[tuple[float, float]] = []
        if row["average_quality"] is not None:
            components.append((weights["quality"], float(row["average_quality"])))
        if row["average_performance_proxy"] is not None and row["performance_samples"] >= 3:
            components.append((weights["performance"], float(row["average_performance_proxy"])))
        if min_latency is not None and row["average_latency_ms"]:
            components.append((weights["latency"], min(1.0, min_latency / float(row["average_latency_ms"]))))
        if min_cost is not None and row["average_cost_usd"] is not None and row["average_cost_usd"] > 0:
            components.append((weights["cost"], min(1.0, min_cost / float(row["average_cost_usd"]))))
        denominator = sum(weight for weight, _ in components)
        row["score"] = round(sum(weight * value for weight, value in components) / denominator, 5) if denominator > 0 else None

    ranked = sorted(
        [row for row in candidate_rows if row["score"] is not None],
        key=lambda row: (float(row["score"]), int(row["samples"])),
        reverse=True,
    )
    recommended = ranked[0]["model"] if ranked else default_model
    return {
        "recommended_model": recommended,
        "routing_ready": len(eligible_rows) >= 2,
        "candidate_count": len(candidate_rows),
        "eligible_count": len(eligible_rows),
        "candidates": candidate_rows,
    }


def deterministic_fraction(run_id: uuid.UUID | str, stage: str) -> float:
    digest = hashlib.sha256(f"{run_id}:{stage}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def choose_from_stage_report(
    report: dict[str, Any],
    *,
    run_id: uuid.UUID | str,
    stage: str,
    default_model: str,
    mode: str,
    exploration_rate: float,
) -> dict[str, Any]:
    family = stage_family(stage)
    if family is None or mode == "off":
        return {
            "mode": mode,
            "stage_family": family,
            "selected_model": default_model,
            "recommended_model": default_model,
            "reason": "routing_disabled_or_stage_not_routed",
            "exploration": False,
            "routing_ready": False,
        }

    recommended = str(report.get("recommended_model") or default_model)
    routing_ready = bool(report.get("routing_ready"))
    exploration = False
    target = recommended
    reason = "best_observed_candidate"

    if mode == "active" and exploration_rate > 0:
        fraction = deterministic_fraction(run_id, family)
        if fraction < exploration_rate:
            candidates = report.get("candidates") or []
            under_sampled = sorted(candidates, key=lambda row: (int(row.get("samples") or 0), str(row.get("model") or "")))
            if under_sampled:
                target = str(under_sampled[0].get("model") or default_model)
                exploration = target != recommended
                reason = "deterministic_exploration"

    if mode == "shadow":
        selected = default_model
        reason = "shadow_only"
    elif mode == "active" and (routing_ready or exploration):
        selected = target
    else:
        selected = default_model
        reason = "insufficient_comparative_evidence"

    return {
        "mode": mode,
        "stage_family": family,
        "selected_model": selected,
        "recommended_model": target,
        "reason": reason,
        "exploration": exploration,
        "routing_ready": routing_ready,
        "candidate_count": int(report.get("candidate_count") or 0),
        "eligible_count": int(report.get("eligible_count") or 0),
    }


async def build_model_router_report(session, project_id: uuid.UUID, *, default_model: str) -> dict[str, Any]:
    candidates = configured_candidates(default_model)
    min_samples = max(3, int(os.getenv("MODEL_ROUTER_MIN_SAMPLES_PER_MODEL", "10")))
    quality_floor = min(1.0, max(0.0, float(os.getenv("MODEL_ROUTER_QUALITY_FLOOR", "0.84"))))

    runs = (await session.execute(select(GenerationRun).where(GenerationRun.project_id == project_id))).scalars().all()
    if not runs:
        empty = score_stage_candidates([], candidates=candidates, default_model=default_model, min_samples=min_samples, quality_floor=quality_floor)
        return {
            "mode": router_mode(),
            "default_model": default_model,
            "configured_candidates": candidates,
            "minimum_samples_per_model": min_samples,
            "quality_floor": quality_floor,
            "exploration_rate": float(os.getenv("MODEL_ROUTER_EXPLORATION_RATE", "0.10")),
            "performance_metric": None,
            "stages": {family: dict(empty) for family in ROUTED_STAGE_FAMILIES},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    run_map = {run.id: run for run in runs}
    run_ids = list(run_map)
    steps = (await session.execute(
        select(GenerationStep)
        .where(GenerationStep.run_id.in_(run_ids), GenerationStep.provider == "openai-compatible")
        .order_by(GenerationStep.created_at.desc())
        .limit(50000)
    )).scalars().all()

    content_ids = {run.content_item_id for run in runs if run.content_item_id}
    snapshots = []
    if content_ids:
        raw = (await session.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.project_id == project_id, PerformanceSnapshot.content_item_id.in_(list(content_ids)))
            .order_by(PerformanceSnapshot.captured_at.desc(), PerformanceSnapshot.created_at.desc())
            .limit(20000)
        )).scalars().all()
        latest: dict[tuple[str, str], PerformanceSnapshot] = {}
        for snapshot in raw:
            latest.setdefault((snapshot.source, snapshot.external_publication_id), snapshot)
        snapshots = [
            {"content_item_id": row.content_item_id, "metrics": row.metrics or {}}
            for row in latest.values()
        ]
    performance_metric, perf_by_content = _performance_scores(snapshots)

    records_by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for step in steps:
        family = stage_family(step.stage)
        if family is None:
            continue
        run = run_map.get(step.run_id)
        if run is None:
            continue
        metas = [meta for meta in extract_provider_meta(step.output_json or {}) if str(meta.get("provider") or step.provider) == "openai-compatible"]
        if not metas:
            metas = [{"model": step.model}]
        for meta in metas:
            model = str(meta.get("model") or step.model or "").strip()
            if not model:
                continue
            records_by_stage[family].append({
                "model": model,
                "quality": run.quality_score,
                "performance": perf_by_content.get(run.content_item_id) if run.content_item_id else None,
                "latency_ms": meta.get("latency_ms"),
                "cost_usd": meta.get("estimated_cost_usd"),
            })

    stages = {
        family: score_stage_candidates(
            records_by_stage.get(family, []),
            candidates=candidates,
            default_model=default_model,
            min_samples=min_samples,
            quality_floor=quality_floor,
        )
        for family in ROUTED_STAGE_FAMILIES
    }
    return {
        "mode": router_mode(),
        "default_model": default_model,
        "configured_candidates": candidates,
        "minimum_samples_per_model": min_samples,
        "quality_floor": quality_floor,
        "exploration_rate": min(0.5, max(0.0, float(os.getenv("MODEL_ROUTER_EXPLORATION_RATE", "0.10")))),
        "performance_metric": performance_metric if snapshots else None,
        "stages": stages,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def choose_model_for_run_stage(session, run: GenerationRun, stage: str, *, default_model: str) -> dict[str, Any]:
    family = stage_family(stage)
    mode = router_mode()
    if family is None or mode == "off":
        return choose_from_stage_report({}, run_id=run.id, stage=stage, default_model=default_model, mode=mode, exploration_rate=0.0)

    options = dict(run.options or {})
    decisions = dict(options.get("_model_router_decisions") or {})
    existing = decisions.get(family)
    if isinstance(existing, dict) and existing.get("selected_model"):
        return existing

    report = await build_model_router_report(session, run.project_id, default_model=default_model)
    stage_report = report.get("stages", {}).get(family) or {}
    decision = choose_from_stage_report(
        stage_report,
        run_id=run.id,
        stage=stage,
        default_model=default_model,
        mode=mode,
        exploration_rate=float(report.get("exploration_rate") or 0.0),
    )
    decision["evidence"] = {
        "minimum_samples_per_model": report.get("minimum_samples_per_model"),
        "quality_floor": report.get("quality_floor"),
        "performance_metric": report.get("performance_metric"),
        "candidates": stage_report.get("candidates") or [],
    }
    decisions[family] = decision
    options["_model_router_decisions"] = decisions
    run.options = options
    await session.flush()
    return decision
