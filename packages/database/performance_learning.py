"""Performance-informed planning helpers.

The learning layer is intentionally deterministic. It treats downstream metrics as a
prior for future planning, not as ground truth, and gates allocation advice by sample
size so a handful of lucky publications cannot collapse exploration.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from .models import ContentItem, GenerationRun, PerformanceSnapshot, ProductionBatchItem, Rubric

MIN_ACTION_SAMPLE = 5
HIGH_CONFIDENCE_SAMPLE = 15
DEFAULT_EXPLORATION_SHARE = 0.25


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _bucket() -> dict[str, float]:
    return {
        "publications": 0.0,
        "views": 0.0,
        "impressions": 0.0,
        "clicks": 0.0,
        "leads": 0.0,
        "conversions": 0.0,
        "revenue": 0.0,
        "reach": 0.0,
    }


def _add(bucket: dict[str, float], metrics: dict[str, Any]) -> None:
    bucket["publications"] += 1
    for key in ("views", "impressions", "clicks", "leads", "conversions", "revenue"):
        bucket[key] += _number(metrics.get(key))
    views = metrics.get("views")
    impressions = metrics.get("impressions")
    bucket["reach"] += _number(views if isinstance(views, (int, float)) else impressions)


def _metric_value(bucket: dict[str, float], metric: str) -> float:
    reach = bucket["reach"]
    if metric == "conversions_per_1000_views":
        return (bucket["conversions"] / reach * 1000) if reach > 0 else 0.0
    if metric == "leads_per_1000_views":
        return (bucket["leads"] / reach * 1000) if reach > 0 else 0.0
    if metric == "ctr":
        return (bucket["clicks"] / reach) if reach > 0 else 0.0
    return (reach / bucket["publications"]) if bucket["publications"] > 0 else 0.0


def _primary_metric(total: dict[str, float]) -> tuple[str, str]:
    if total["conversions"] > 0 and total["reach"] > 0:
        return "conversions_per_1000_views", "conversions / 1k views"
    if total["leads"] > 0 and total["reach"] > 0:
        return "leads_per_1000_views", "leads / 1k views"
    if total["clicks"] > 0 and total["reach"] > 0:
        return "ctr", "CTR"
    return "views_per_publication", "views / publication"


def _confidence(publications: int) -> str:
    if publications >= HIGH_CONFIDENCE_SAMPLE:
        return "high"
    if publications >= MIN_ACTION_SAMPLE:
        return "medium"
    return "low"


def _segment_rows(
    dimension: str,
    buckets: dict[str, dict[str, float]],
    *,
    metric: str,
    baseline: float,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name, bucket in buckets.items():
        publications = int(bucket["publications"])
        value = _metric_value(bucket, metric)
        lift = ((value / baseline) - 1.0) if baseline > 0 else None
        confidence = _confidence(publications)
        if publications < MIN_ACTION_SAMPLE:
            action = "explore"
        elif lift is not None and lift >= 0.15:
            action = "scale_cautiously"
        elif lift is not None and lift <= -0.20:
            action = "reduce_and_retest"
        else:
            action = "keep_testing"
        result.append({
            "dimension": dimension,
            "name": name,
            "publications": publications,
            "metric_value": round(value, 6),
            "lift_vs_baseline": round(lift, 4) if lift is not None else None,
            "confidence": confidence,
            "action": action,
            "totals": {
                "views": int(bucket["views"]),
                "impressions": int(bucket["impressions"]),
                "clicks": int(bucket["clicks"]),
                "leads": int(bucket["leads"]),
                "conversions": int(bucket["conversions"]),
                "revenue": round(bucket["revenue"], 2),
            },
        })
    return sorted(result, key=lambda row: (row["metric_value"], row["publications"]), reverse=True)


def derive_learning_context(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a compact, planner-safe learning snapshot from latest publication rows."""
    total = _bucket()
    dimensions: dict[str, dict[str, dict[str, float]]] = {
        "content_type": defaultdict(_bucket),
        "rubric": defaultdict(_bucket),
        "platform": defaultdict(_bucket),
    }
    for record in records:
        metrics = record.get("metrics") or {}
        _add(total, metrics)
        _add(dimensions["content_type"][str(record.get("content_type") or "other")], metrics)
        _add(dimensions["rubric"][str(record.get("rubric") or "Unassigned")], metrics)
        _add(dimensions["platform"][str(record.get("platform") or "unknown")], metrics)

    metric, label = _primary_metric(total)
    baseline = _metric_value(total, metric)
    ranked = {
        name: _segment_rows(name, buckets, metric=metric, baseline=baseline)
        for name, buckets in dimensions.items()
    }
    publications = int(total["publications"])
    actionable = publications >= MIN_ACTION_SAMPLE
    winners = [
        row for dimension in ranked.values() for row in dimension
        if row["action"] == "scale_cautiously"
    ][:5]
    watch = [
        row for dimension in ranked.values() for row in reversed(dimension)
        if row["action"] == "reduce_and_retest"
    ][:5]

    guidance: list[str] = []
    if not actionable:
        guidance.append(
            f"Only {publications} publication(s) have usable downstream data; do not optimize allocation yet. Collect at least {MIN_ACTION_SAMPLE}."
        )
    else:
        guidance.append(
            f"Use historical {label} as a prior, not a rule. Keep at least {int(DEFAULT_EXPLORATION_SHARE * 100)}% of the batch for genuinely new angles/rubrics."
        )
        if winners:
            names = ", ".join(f"{row['dimension']}={row['name']}" for row in winners[:3])
            guidance.append(f"Cautiously allocate more tests to: {names}.")
        if watch:
            names = ", ".join(f"{row['dimension']}={row['name']}" for row in watch[:3])
            guidance.append(f"Reduce repetition and retest with a different angle before abandoning: {names}.")

    return {
        "status": "learning" if actionable else "insufficient_data",
        "publications": publications,
        "primary_metric": metric,
        "primary_metric_label": label,
        "baseline": round(baseline, 6),
        "exploration_share": DEFAULT_EXPLORATION_SHARE,
        "by_content_type": ranked["content_type"],
        "by_rubric": ranked["rubric"],
        "by_platform": ranked["platform"],
        "recommendations": {"winners": winners, "watch": watch, "guidance": guidance},
    }


async def build_performance_learning_context(session, project_id: uuid.UUID, *, limit: int = 20000) -> dict[str, Any]:
    items = (await session.execute(select(ContentItem).where(ContentItem.project_id == project_id))).scalars().all()
    if not items:
        return derive_learning_context([])
    item_map = {item.id: item for item in items}

    snapshots = (
        await session.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.project_id == project_id)
            .order_by(PerformanceSnapshot.captured_at.desc(), PerformanceSnapshot.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    latest: dict[tuple[str, str], PerformanceSnapshot] = {}
    for snapshot in snapshots:
        latest.setdefault((snapshot.source, snapshot.external_publication_id), snapshot)

    runs = (
        await session.execute(select(GenerationRun).where(GenerationRun.content_item_id.in_(list(item_map.keys()))))
    ).scalars().all()
    run_by_content = {run.content_item_id: run for run in runs if run.content_item_id}
    batch_items = []
    if runs:
        batch_items = (
            await session.execute(select(ProductionBatchItem).where(ProductionBatchItem.child_run_id.in_([run.id for run in runs])))
        ).scalars().all()
    batch_by_run = {row.child_run_id: row for row in batch_items if row.child_run_id}
    rubric_ids = {row.rubric_id for row in batch_items if row.rubric_id}
    rubric_names: dict[uuid.UUID, str] = {}
    if rubric_ids:
        rows = (await session.execute(select(Rubric).where(Rubric.id.in_(rubric_ids)))).scalars().all()
        rubric_names = {row.id: row.name for row in rows}

    records: list[dict[str, Any]] = []
    for snapshot in latest.values():
        item = item_map.get(snapshot.content_item_id)
        if not item:
            continue
        run = run_by_content.get(item.id)
        batch_item = batch_by_run.get(run.id) if run else None
        rubric = rubric_names.get(batch_item.rubric_id, "Unassigned") if batch_item else "Unassigned"
        content_type = item.type.value if hasattr(item.type, "value") else str(item.type)
        records.append({
            "content_type": content_type,
            "rubric": rubric,
            "platform": snapshot.platform,
            "metrics": snapshot.metrics or {},
        })
    return derive_learning_context(records)
