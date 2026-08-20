"""Performance-informed planning helpers.

Downstream outcomes are treated as noisy priors, never causal truth. The business metric is
project-configured and stable; it does not change just because the first click/lead/conversion
arrived.

Only snapshots with immutable Factory delivery lineage participate in allocation learning.
Legacy / content-package/1.0 snapshots remain visible in analytics but are excluded from
high-confidence optimization. Rubric/batch/run attribution is read from the snapshot itself,
never reconstructed from the latest GenerationRun for a ContentItem.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from .models import ContentItem, PerformanceSnapshot, Project, Rubric

MIN_ACTION_SAMPLE = 5
HIGH_CONFIDENCE_MULTIPLIER = 3
DEFAULT_EXPLORATION_SHARE = 0.25
SUPPORTED_PRIMARY_METRICS = {
    "views_per_publication",
    "ctr",
    "leads_per_1000_views",
    "conversions_per_1000_views",
}


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


def _confidence(publications: int, minimum: int) -> str:
    if publications >= max(minimum * HIGH_CONFIDENCE_MULTIPLIER, 30):
        return "high"
    if publications >= minimum:
        return "medium"
    return "low"


def _segment_rows(
    dimension: str,
    buckets: dict[str, dict[str, float]],
    *,
    metric: str,
    baseline: float,
    minimum: int,
    allocatable: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name, bucket in buckets.items():
        publications = int(bucket["publications"])
        value = _metric_value(bucket, metric)
        lift = ((value / baseline) - 1.0) if baseline > 0 else None
        confidence = _confidence(publications, minimum)
        if not allocatable:
            action = "context_only"
        elif publications < minimum:
            action = "explore"
        elif lift is not None and lift >= 0.15:
            action = "scale_cautiously"
        elif lift is not None and lift <= -0.20:
            action = "reduce_and_retest"
        else:
            action = "keep_testing"
        result.append(
            {
                "dimension": dimension,
                "name": name,
                "publications": publications,
                "metric_value": round(value, 6),
                "lift_vs_baseline": round(lift, 4) if lift is not None else None,
                "confidence": confidence,
                "action": action,
                "totals": {
                    key: (round(bucket[key], 2) if key == "revenue" else int(bucket[key]))
                    for key in ("views", "impressions", "clicks", "leads", "conversions", "revenue")
                },
            }
        )
    return sorted(result, key=lambda row: (row["metric_value"], row["publications"]), reverse=True)


def derive_learning_context(
    records: list[dict[str, Any]],
    *,
    primary_metric: str = "views_per_publication",
    min_action_sample: int = 10,
    exploration_share: float = DEFAULT_EXPLORATION_SHARE,
    excluded_untrusted_publications: int = 0,
) -> dict[str, Any]:
    metric = primary_metric if primary_metric in SUPPORTED_PRIMARY_METRICS else "views_per_publication"
    minimum = max(MIN_ACTION_SAMPLE, int(min_action_sample))
    exploration = min(0.50, max(0.05, float(exploration_share)))
    total = _bucket()
    dimensions: dict[str, dict[str, dict[str, float]]] = {
        "content_type": defaultdict(_bucket),
        "rubric": defaultdict(_bucket),
        "platform": defaultdict(_bucket),
        "account": defaultdict(_bucket),
    }
    for record in records:
        metrics = record.get("metrics") or {}
        _add(total, metrics)
        _add(dimensions["content_type"][str(record.get("content_type") or "other")], metrics)
        _add(dimensions["rubric"][str(record.get("rubric") or "Unassigned")], metrics)
        _add(dimensions["platform"][str(record.get("platform") or "unknown")], metrics)
        _add(dimensions["account"][str(record.get("account_id") or "unknown")], metrics)

    baseline = _metric_value(total, metric)
    ranked = {
        name: _segment_rows(
            name,
            buckets,
            metric=metric,
            baseline=baseline,
            minimum=minimum,
            allocatable=name in {"content_type", "rubric"},
        )
        for name, buckets in dimensions.items()
    }
    publications = int(total["publications"])
    actionable = publications >= minimum
    allocation_rows = ranked["content_type"] + ranked["rubric"]
    winners = [row for row in allocation_rows if row["action"] == "scale_cautiously"][:5]
    watch = [row for row in reversed(allocation_rows) if row["action"] == "reduce_and_retest"][:5]

    guidance: list[str] = []
    if excluded_untrusted_publications:
        guidance.append(
            f"{excluded_untrusted_publications} publication(s) lack immutable Factory delivery lineage "
            "and are excluded from allocation learning."
        )
    if not actionable:
        guidance.append(
            f"Only {publications} trusted publication(s) have usable downstream data; "
            f"collect at least {minimum} before allocation changes."
        )
    else:
        guidance.append(
            f"Optimize the configured metric {metric}; keep at least "
            f"{int(exploration * 100)}% for genuinely new content hypotheses."
        )
        guidance.append(
            "Platform/account rows are context diagnostics only; never infer that a rubric won "
            "merely because it was distributed on a stronger account."
        )
        if winners:
            guidance.append(
                "Cautiously allocate more tests to: "
                + ", ".join(f"{row['dimension']}={row['name']}" for row in winners[:3])
                + "."
            )
        if watch:
            guidance.append(
                "Reduce repetition and retest: "
                + ", ".join(f"{row['dimension']}={row['name']}" for row in watch[:3])
                + "."
            )

    return {
        "status": "learning" if actionable else "insufficient_data",
        "publications": publications,
        "trusted_publications": publications,
        "excluded_untrusted_publications": int(excluded_untrusted_publications),
        "lineage_policy": "immutable_delivery_required",
        "primary_metric": metric,
        "primary_metric_label": metric.replace("_", " "),
        "baseline": round(baseline, 6),
        "exploration_share": exploration,
        "min_action_sample": minimum,
        "by_content_type": ranked["content_type"],
        "by_rubric": ranked["rubric"],
        "by_platform": ranked["platform"],
        "by_account": ranked["account"],
        "recommendations": {"winners": winners, "watch": watch, "guidance": guidance},
    }


async def build_performance_learning_context(
    session,
    project_id: uuid.UUID,
    *,
    limit: int = 20000,
) -> dict[str, Any]:
    project = await session.get(Project, project_id)
    if project is None:
        return derive_learning_context([])

    items = (
        await session.execute(select(ContentItem).where(ContentItem.project_id == project_id))
    ).scalars().all()
    if not items:
        return derive_learning_context(
            [],
            primary_metric=project.learning_primary_metric,
            min_action_sample=project.learning_min_publications,
            exploration_share=project.learning_exploration_share,
        )
    item_map = {item.id: item for item in items}

    snapshots = (
        await session.execute(
            select(PerformanceSnapshot)
            .where(PerformanceSnapshot.project_id == project_id)
            .order_by(
                PerformanceSnapshot.captured_at.desc(),
                PerformanceSnapshot.created_at.desc(),
            )
            .limit(limit)
        )
    ).scalars().all()

    latest: dict[tuple[str, str], PerformanceSnapshot] = {}
    for snapshot in snapshots:
        latest.setdefault((snapshot.source, snapshot.external_publication_id), snapshot)

    trusted: list[PerformanceSnapshot] = []
    excluded_untrusted = 0
    for snapshot in latest.values():
        # content-package/1.1 snapshots carry a frozen Factory delivery id + payload digest.
        # Legacy / incomplete callbacks are analytics-only and must not drive allocation.
        if snapshot.export_delivery_id is None or not snapshot.payload_sha256 or snapshot.content_version is None:
            excluded_untrusted += 1
            continue
        trusted.append(snapshot)

    rubric_ids = {snapshot.rubric_id for snapshot in trusted if snapshot.rubric_id}
    rubric_names: dict[uuid.UUID, str] = {}
    if rubric_ids:
        rows = (
            await session.execute(
                select(Rubric).where(
                    Rubric.id.in_(rubric_ids),
                    Rubric.project_id == project_id,
                )
            )
        ).scalars().all()
        rubric_names = {row.id: row.name for row in rows}

    records: list[dict[str, Any]] = []
    for snapshot in trusted:
        item = item_map.get(snapshot.content_item_id)
        if item is None:
            # The FK should prevent this, but fail closed for learning if historical data is inconsistent.
            excluded_untrusted += 1
            continue
        content_type = item.type.value if hasattr(item.type, "value") else str(item.type)
        metadata = snapshot.metadata_json or {}
        rubric = (
            rubric_names.get(snapshot.rubric_id, f"rubric:{snapshot.rubric_id}")
            if snapshot.rubric_id
            else "Unassigned"
        )
        records.append(
            {
                "content_type": content_type,
                "rubric": rubric,
                "platform": snapshot.platform,
                "account_id": metadata.get("account_id"),
                "metrics": snapshot.metrics or {},
                # Exact immutable lineage is retained in the record for future contextual models.
                "generation_run_id": str(snapshot.generation_run_id) if snapshot.generation_run_id else None,
                "batch_id": str(snapshot.batch_id) if snapshot.batch_id else None,
                "rubric_id": str(snapshot.rubric_id) if snapshot.rubric_id else None,
                "content_version": snapshot.content_version,
                "export_delivery_id": str(snapshot.export_delivery_id),
                "prompt_version": snapshot.prompt_version,
                "prompt_hash": snapshot.prompt_hash,
                "model": snapshot.model,
            }
        )

    return derive_learning_context(
        records,
        primary_metric=project.learning_primary_metric,
        min_action_sample=project.learning_min_publications,
        exploration_share=project.learning_exploration_share,
        excluded_untrusted_publications=excluded_untrusted,
    )
