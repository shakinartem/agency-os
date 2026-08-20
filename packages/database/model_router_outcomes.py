"""Outcome gate on top of shadow/live Model Router evidence.

Content-producing stages may only receive full non-default routing after real downstream
performance has returned for enough live samples. Strategy/planning stages do not pretend to
have direct causal publication attribution and therefore keep the live+quality gate only.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from .model_router_evidence import build_model_router_report as build_evidence_report

OUTCOME_GATED_STAGE_FAMILIES = {"draft", "evaluate", "revise", "humanize", "adapt"}


def apply_outcome_gates(
    report: dict[str, Any],
    *,
    default_model: str,
    minimum_downstream_samples: int,
) -> dict[str, Any]:
    stages = report.get("stages") or {}
    for family, stage in stages.items():
        candidates = stage.get("candidates") or []
        requires_outcomes = family in OUTCOME_GATED_STAGE_FAMILIES
        for row in candidates:
            model = str(row.get("model") or "")
            base_eligible = bool(row.get("eligible"))
            live_ok = int(row.get("live_samples") or 0) >= int(report.get("minimum_live_samples") or 1)
            outcome_ok = (
                int(row.get("performance_samples") or 0) >= minimum_downstream_samples
                if requires_outcomes
                else True
            )
            row["requires_downstream_outcomes"] = requires_outcomes
            row["downstream_gate_passed"] = model == default_model or outcome_ok
            row["production_eligible"] = bool(
                base_eligible and (model == default_model or (live_ok and outcome_ok))
            )

        ranked = sorted(
            [row for row in candidates if row.get("production_eligible") and row.get("score") is not None],
            key=lambda row: (
                float(row.get("score") or 0),
                int(row.get("performance_samples") or 0),
                int(row.get("live_samples") or 0),
            ),
            reverse=True,
        )
        stage["recommended_model"] = ranked[0]["model"] if ranked else default_model
        stage["routing_ready"] = len(ranked) >= 2
        stage["production_eligible_count"] = len(ranked)
        stage["outcome_gate_required"] = requires_outcomes

    report["minimum_downstream_samples"] = minimum_downstream_samples
    report["outcome_gated_stages"] = sorted(OUTCOME_GATED_STAGE_FAMILIES)
    return report


async def build_model_router_report(session, project_id: uuid.UUID, *, default_model: str) -> dict[str, Any]:
    report = await build_evidence_report(session, project_id, default_model=default_model)
    minimum_downstream_samples = max(1, int(os.getenv("MODEL_ROUTER_MIN_DOWNSTREAM_SAMPLES", "3")))
    return apply_outcome_gates(
        report,
        default_model=default_model,
        minimum_downstream_samples=minimum_downstream_samples,
    )
