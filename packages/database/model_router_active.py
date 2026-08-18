"""Traffic policy for cached evidence-aware Model Router."""
from __future__ import annotations

from typing import Any

from .model_router import choose_from_stage_report, router_mode, stage_family
from .model_router_cache import get_cached_model_router_report


async def choose_model_for_run_stage(session, run, stage: str, *, default_model: str) -> dict[str, Any]:
    family = stage_family(stage)
    mode = router_mode()
    if family is None or mode == "off":
        return choose_from_stage_report({}, run_id=run.id, stage=stage, default_model=default_model, mode=mode, exploration_rate=0.0)

    options = dict(run.options or {})
    decisions = dict(options.get("_model_router_decisions") or {})
    existing = decisions.get(family)
    if isinstance(existing, dict) and existing.get("selected_model"):
        return existing

    report = options.get("_model_router_report")
    if not isinstance(report, dict) or report.get("default_model") != default_model:
        report = await get_cached_model_router_report(
            session,
            run.project_id,
            default_model=default_model,
            schedule_refresh=True,
        )
        options["_model_router_report"] = report

    stage_report = dict((report.get("stages") or {}).get(family) or {})
    all_candidates = list(stage_report.get("candidates") or [])
    if mode == "shadow":
        stage_report["recommended_model"] = stage_report.get("shadow_recommended_model") or default_model
    elif mode == "active":
        stage_report["candidates"] = [
            row for row in all_candidates
            if str(row.get("model") or "") == default_model or bool(row.get("eligible"))
        ]

    decision = choose_from_stage_report(
        stage_report,
        run_id=run.id,
        stage=stage,
        default_model=default_model,
        mode=mode,
        exploration_rate=float(report.get("exploration_rate") or 0.0),
    )
    decision["shadow_sample_rate"] = float(report.get("shadow_sample_rate") or 0.0)
    decision["cache"] = report.get("cache") or {}
    decision["evidence"] = {
        "minimum_samples_per_model": report.get("minimum_samples_per_model"),
        "minimum_live_samples": report.get("minimum_live_samples"),
        "minimum_downstream_samples": report.get("minimum_downstream_samples"),
        "quality_floor": report.get("quality_floor"),
        "performance_metric": report.get("performance_metric"),
        "candidates": all_candidates,
    }
    decisions[family] = decision
    options["_model_router_decisions"] = decisions
    run.options = options
    await session.flush()
    return decision
