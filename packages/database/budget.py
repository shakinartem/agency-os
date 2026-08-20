"""Generation budget guardrails backed by persisted provider telemetry."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from .generation_economics import aggregate_generation_economics
from .models import GenerationRun, GenerationStep


class BudgetExceeded(RuntimeError):
    pass


def _limit(name: str) -> float:
    try: return max(0.0, float(os.getenv(name, "0") or 0))
    except ValueError: return 0.0


def _month_start(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


async def _economics_for_steps(session, stmt) -> dict:
    steps = (await session.execute(stmt)).scalars().all()
    return aggregate_generation_economics([
        {"stage": step.stage, "provider": step.provider, "model": step.model, "output_json": step.output_json or {}}
        for step in steps
    ])


async def enforce_generation_budget(session, run: GenerationRun) -> dict:
    """Fail before the next paid stage when configured known-cost budgets are exhausted."""
    run_limit = _limit("GENERATION_MAX_RUN_COST_USD")
    daily_limit = _limit("GENERATION_DAILY_BUDGET_USD")
    monthly_limit = _limit("GENERATION_MONTHLY_BUDGET_USD")
    if not any((run_limit, daily_limit, monthly_limit)):
        return {"enabled": False}

    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    month_start = _month_start(now)
    require_pricing = os.getenv("GENERATION_BUDGET_REQUIRE_PRICING", "true").strip().lower() in {"1", "true", "yes", "on"}

    run_report = await _economics_for_steps(session, select(GenerationStep).where(GenerationStep.run_id == run.id))
    day_report = await _economics_for_steps(
        session,
        select(GenerationStep).join(GenerationRun, GenerationRun.id == GenerationStep.run_id).where(
            GenerationRun.project_id == run.project_id, GenerationStep.created_at >= day_start,
        ).limit(50000),
    )
    month_report = await _economics_for_steps(
        session,
        select(GenerationStep).join(GenerationRun, GenerationRun.id == GenerationStep.run_id).where(
            GenerationRun.project_id == run.project_id, GenerationStep.created_at >= month_start,
        ).limit(200000),
    )

    reports = {"run": run_report, "day": day_report, "month": month_report}
    if require_pricing and any(report.get("unpriced_requests", 0) for report in reports.values()):
        raise BudgetExceeded("Generation budget is enabled but provider pricing is incomplete")

    checks = [
        ("run", run_limit, run_report.get("known_cost_usd", 0.0)),
        ("day", daily_limit, day_report.get("known_cost_usd", 0.0)),
        ("month", monthly_limit, month_report.get("known_cost_usd", 0.0)),
    ]
    for scope, limit, spent in checks:
        if limit > 0 and float(spent or 0) >= limit:
            raise BudgetExceeded(f"Generation {scope} budget exhausted: ${float(spent):.4f} >= ${limit:.4f}")
    return {"enabled": True, "limits": {"run": run_limit, "day": daily_limit, "month": monthly_limit}, "reports": reports}
