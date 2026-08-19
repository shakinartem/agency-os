"""Shadow prompt/model experiment assignment, persistence helpers and reporting.

Experiments are intentionally isolated from Model Router evidence. A candidate arm may change
both prompt and model, so attributing its win to the model alone would be statistically wrong.
The control response remains the production response; candidate output is never user-visible.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .model_router import ROUTED_STAGE_FAMILIES, deterministic_fraction
from .model_router_prompt import current_content_prompt_version
from .models import PromptExperiment, PromptExperimentArm, PromptExperimentObservation

MAX_SHADOW_SAMPLE_RATE = 0.25
ALLOWED_EXPERIMENT_STATUSES = {"draft", "shadow", "paused", "completed"}


def candidate_prompt_version(control_prompt_version: str, experiment_id: uuid.UUID | str, arm_key: str) -> str:
    return f"{control_prompt_version}+exp:{str(experiment_id)[:8]}:{arm_key}"[:180]


def choose_arm_index(run_id: uuid.UUID | str, experiment_id: uuid.UUID | str, arm_count: int) -> int:
    if arm_count <= 0:
        raise ValueError("arm_count must be positive")
    fraction = deterministic_fraction(run_id, f"prompt-experiment-arm:{experiment_id}")
    return min(arm_count - 1, int(fraction * arm_count))


def _compatible_content_type(experiment: PromptExperiment, content_type: str | None) -> bool:
    allowed = [str(value) for value in (experiment.content_types or []) if value]
    return not allowed or (content_type is not None and content_type in allowed)


def _assignment_from_rows(experiment: PromptExperiment, arm: PromptExperimentArm) -> dict[str, Any]:
    return {
        "experiment_id": str(experiment.id),
        "experiment_name": experiment.name,
        "arm_id": str(arm.id),
        "arm_key": arm.key,
        "arm_name": arm.name,
        "candidate_model": arm.model,
        "control_prompt_version": experiment.control_prompt_version,
        "candidate_prompt_version": candidate_prompt_version(experiment.control_prompt_version, experiment.id, arm.key),
        "system_append": arm.system_append or "",
        "prompt_append": arm.prompt_append or "",
        "sample_rate": float(experiment.sample_rate),
        "primary_metric": experiment.primary_metric,
    }


async def resolve_shadow_experiment_assignment(
    session: AsyncSession,
    run,
    stage_family: str | None,
) -> dict[str, Any] | None:
    """Return one retry-stable shadow arm assignment for a run/stage family.

    Existing in-flight assignments survive experiment pause so retries are comparable. A prompt
    cohort deployment change invalidates the assignment rather than mixing prompt versions.
    """
    if stage_family not in ROUTED_STAGE_FAMILIES:
        return None

    options = dict(run.options or {})
    completed = set(str(value) for value in (options.get("_prompt_experiment_completed_families") or []))
    if stage_family in completed:
        return None

    assignments = dict(options.get("_prompt_experiment_assignments") or {})
    existing = assignments.get(stage_family)
    if isinstance(existing, dict) and existing.get("experiment_id") and existing.get("arm_id"):
        if existing.get("control_prompt_version") != current_content_prompt_version():
            return None
        return dict(existing)

    experiment = await session.scalar(
        select(PromptExperiment)
        .where(
            PromptExperiment.project_id == run.project_id,
            PromptExperiment.stage_family == stage_family,
            PromptExperiment.status == "shadow",
        )
        .order_by(PromptExperiment.started_at.asc().nulls_last(), PromptExperiment.created_at.asc())
        .limit(1)
    )
    if experiment is None:
        return None
    if experiment.control_prompt_version != current_content_prompt_version():
        return None
    if not _compatible_content_type(experiment, getattr(run, "content_type", None)):
        return None

    observed = await session.scalar(
        select(PromptExperimentObservation.id).where(
            PromptExperimentObservation.experiment_id == experiment.id,
            PromptExperimentObservation.run_id == run.id,
            PromptExperimentObservation.stage_family == stage_family,
        )
    )
    if observed is not None:
        completed.add(stage_family)
        options["_prompt_experiment_completed_families"] = sorted(completed)
        run.options = options
        await session.flush()
        return None

    sample_rate = min(MAX_SHADOW_SAMPLE_RATE, max(0.0, float(experiment.sample_rate or 0.0)))
    if sample_rate <= 0:
        return None
    if deterministic_fraction(run.id, f"prompt-experiment:{experiment.id}:{stage_family}") >= sample_rate:
        return None

    arms = (
        await session.execute(
            select(PromptExperimentArm)
            .where(PromptExperimentArm.experiment_id == experiment.id, PromptExperimentArm.active.is_(True))
            .order_by(PromptExperimentArm.key.asc())
        )
    ).scalars().all()
    if not arms:
        return None

    arm = arms[choose_arm_index(run.id, experiment.id, len(arms))]
    assignment = _assignment_from_rows(experiment, arm)
    assignments[stage_family] = assignment
    options["_prompt_experiment_assignments"] = assignments
    run.options = options
    await session.flush()
    return assignment


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def summarize_arm_observations(observations: Iterable[Any], min_samples: int) -> dict[str, Any]:
    rows = list(observations)
    passed = [row for row in rows if getattr(row, "status", None) == "passed"]
    valid = [row for row in passed if _number(getattr(row, "quality_delta", None)) is not None]
    candidate_wins = sum(1 for row in valid if getattr(row, "winner", None) == "candidate")
    control_wins = sum(1 for row in valid if getattr(row, "winner", None) == "production")
    ties = sum(1 for row in valid if getattr(row, "winner", None) == "tie")
    decisive = candidate_wins + control_wins
    deltas = [float(row.quality_delta) for row in valid]
    candidate_quality = [float(row.candidate_quality) for row in valid if _number(getattr(row, "candidate_quality", None)) is not None]
    control_quality = [float(row.control_quality) for row in valid if _number(getattr(row, "control_quality", None)) is not None]
    latencies = [float(row.candidate_latency_ms) for row in rows if _number(getattr(row, "candidate_latency_ms", None)) is not None]
    costs = [float(row.candidate_cost_usd) for row in rows if _number(getattr(row, "candidate_cost_usd", None)) is not None]

    samples = len(valid)
    failure_rate = (len(rows) - len(passed)) / len(rows) if rows else 0.0
    average_delta = sum(deltas) / len(deltas) if deltas else None
    candidate_win_rate = candidate_wins / decisive if decisive else None

    if samples < min_samples:
        decision = "collecting"
    elif failure_rate > 0.10:
        decision = "reject_reliability"
    elif average_delta is not None and average_delta >= 0.02 and candidate_win_rate is not None and candidate_win_rate >= 0.55:
        decision = "promising"
    elif average_delta is not None and average_delta <= -0.02 and candidate_win_rate is not None and candidate_win_rate <= 0.45:
        decision = "reject"
    else:
        decision = "inconclusive"

    confidence = "low"
    if samples >= max(min_samples * 3, 60):
        confidence = "high"
    elif samples >= min_samples:
        confidence = "medium"

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "observations": len(rows),
        "valid_samples": samples,
        "failed_samples": len(rows) - len(passed),
        "candidate_wins": candidate_wins,
        "control_wins": control_wins,
        "ties": ties,
        "candidate_win_rate": round(candidate_win_rate, 4) if candidate_win_rate is not None else None,
        "average_quality_delta": round(average_delta, 4) if average_delta is not None else None,
        "average_candidate_quality": round(mean(candidate_quality), 4) if candidate_quality else None,
        "average_control_quality": round(mean(control_quality), 4) if control_quality else None,
        "average_candidate_latency_ms": round(mean(latencies)) if latencies else None,
        "average_candidate_cost_usd": round(mean(costs), 8) if costs else None,
        "failure_rate": round(failure_rate, 4),
        "confidence": confidence,
        "decision": decision,
    }


async def build_prompt_experiment_report(session: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
    experiments = (
        await session.execute(
            select(PromptExperiment)
            .where(PromptExperiment.project_id == project_id)
            .order_by(PromptExperiment.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    if not experiments:
        return {
            "project_id": str(project_id),
            "current_prompt_version": current_content_prompt_version(),
            "auto_promotion": False,
            "max_shadow_sample_rate": MAX_SHADOW_SAMPLE_RATE,
            "experiments": [],
        }

    experiment_ids = [row.id for row in experiments]
    arms = (
        await session.execute(
            select(PromptExperimentArm)
            .where(PromptExperimentArm.experiment_id.in_(experiment_ids))
            .order_by(PromptExperimentArm.key.asc())
        )
    ).scalars().all()
    observations = (
        await session.execute(
            select(PromptExperimentObservation)
            .where(PromptExperimentObservation.experiment_id.in_(experiment_ids))
            .order_by(PromptExperimentObservation.created_at.desc())
            .limit(10000)
        )
    ).scalars().all()

    arms_by_experiment: dict[uuid.UUID, list[PromptExperimentArm]] = defaultdict(list)
    observations_by_arm: dict[uuid.UUID, list[PromptExperimentObservation]] = defaultdict(list)
    for arm in arms:
        arms_by_experiment[arm.experiment_id].append(arm)
    for observation in observations:
        observations_by_arm[observation.arm_id].append(observation)

    current_prompt = current_content_prompt_version()
    result = []
    for experiment in experiments:
        arm_rows = []
        for arm in arms_by_experiment.get(experiment.id, []):
            summary = summarize_arm_observations(observations_by_arm.get(arm.id, []), experiment.min_samples)
            arm_rows.append({
                "id": str(arm.id),
                "key": arm.key,
                "name": arm.name,
                "model": arm.model,
                "system_append": arm.system_append or "",
                "prompt_append": arm.prompt_append or "",
                "candidate_prompt_version": candidate_prompt_version(experiment.control_prompt_version, experiment.id, arm.key),
                **summary,
            })
        ranked = sorted(
            [row for row in arm_rows if row["decision"] == "promising" and row["average_quality_delta"] is not None],
            key=lambda row: (float(row["average_quality_delta"]), int(row["valid_samples"])),
            reverse=True,
        )
        result.append({
            "id": str(experiment.id),
            "name": experiment.name,
            "hypothesis": experiment.hypothesis,
            "stage_family": experiment.stage_family,
            "content_types": experiment.content_types or [],
            "status": experiment.status,
            "sample_rate": experiment.sample_rate,
            "min_samples": experiment.min_samples,
            "primary_metric": experiment.primary_metric,
            "control_prompt_version": experiment.control_prompt_version,
            "compatible_with_current_prompt": experiment.control_prompt_version == current_prompt,
            "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
            "recommendation": ranked[0]["key"] if ranked else None,
            "arms": arm_rows,
        })

    return {
        "project_id": str(project_id),
        "current_prompt_version": current_prompt,
        "auto_promotion": False,
        "max_shadow_sample_rate": MAX_SHADOW_SAMPLE_RATE,
        "experiments": result,
    }


def observation_values(
    *,
    assignment: dict[str, Any],
    trace: dict[str, Any],
    run,
    step,
    control_model: str,
) -> dict[str, Any]:
    candidate_meta = trace.get("candidate_provider_meta") if isinstance(trace.get("candidate_provider_meta"), dict) else {}
    control_quality = _number(trace.get("production_quality"))
    candidate_quality = _number(trace.get("candidate_quality"))
    delta = candidate_quality - control_quality if candidate_quality is not None and control_quality is not None else None
    candidate_model = str(trace.get("candidate_model") or assignment.get("candidate_model") or control_model)
    return {
        "id": uuid.uuid4(),
        "experiment_id": uuid.UUID(str(assignment["experiment_id"])),
        "arm_id": uuid.UUID(str(assignment["arm_id"])),
        "run_id": run.id,
        "generation_step_id": step.id,
        "content_item_id": getattr(run, "content_item_id", None),
        "stage_family": str(assignment.get("stage_family") or ""),
        "status": str(trace.get("status") or "unknown"),
        "control_model": control_model,
        "candidate_model": candidate_model,
        "control_prompt_version": str(assignment.get("control_prompt_version") or current_content_prompt_version()),
        "candidate_prompt_version": str(assignment.get("candidate_prompt_version") or "unknown"),
        "winner": trace.get("winner"),
        "control_quality": control_quality,
        "candidate_quality": candidate_quality,
        "quality_delta": delta,
        "candidate_latency_ms": int(candidate_meta["latency_ms"]) if _number(candidate_meta.get("latency_ms")) is not None else None,
        "candidate_cost_usd": _number(candidate_meta.get("estimated_cost_usd")),
        "production_output_hash": trace.get("production_output_hash"),
        "candidate_output_hash": trace.get("candidate_output_hash"),
        "metadata_json": {
            "judge_model": trace.get("judge_model"),
            "judge_order": trace.get("judge_order"),
            "notes": trace.get("notes") or [],
            "evidence_scope": "prompt_experiment",
        },
    }


async def stage_prompt_experiment_observation(
    session: AsyncSession,
    *,
    assignment: dict[str, Any],
    trace: dict[str, Any],
    run,
    step,
    control_model: str,
) -> None:
    """Stage an idempotent observation in the same transaction as GenerationStep completion."""
    values = observation_values(
        assignment=assignment,
        trace=trace,
        run=run,
        step=step,
        control_model=control_model,
    )
    stmt = insert(PromptExperimentObservation).values(**values).on_conflict_do_nothing(
        constraint="uq_prompt_experiment_observation_run_stage"
    )
    await session.execute(stmt)

    options = dict(run.options or {})
    completed = set(str(value) for value in (options.get("_prompt_experiment_completed_families") or []))
    completed.add(str(assignment.get("stage_family") or ""))
    options["_prompt_experiment_completed_families"] = sorted(value for value in completed if value)
    run.options = options
    await session.flush()
