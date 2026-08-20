import uuid
from types import SimpleNamespace

from database.model_router_evidence import _score_with_evidence_gates, records_from_step


def record(model: str, quality: float, source: str, *, cost: float = 0.01):
    return {
        "model": model,
        "quality": quality,
        "performance": 0.6 if source == "live" else None,
        "latency_ms": 500,
        "cost_usd": cost,
        "evidence_source": source,
    }


def test_shadow_candidate_cannot_receive_full_routing_without_live_samples():
    rows = [
        *[record("default", 0.90, "live") for _ in range(12)],
        *[record("candidate", 0.96, "shadow", cost=0.002) for _ in range(12)],
    ]
    report = _score_with_evidence_gates(
        rows,
        candidates=["default", "candidate"],
        default_model="default",
        min_samples=10,
        min_live_samples=3,
        quality_floor=0.84,
    )
    candidate = next(row for row in report["candidates"] if row["model"] == "candidate")
    assert candidate["eligible"] is True
    assert candidate["shadow_samples"] == 12
    assert candidate["live_samples"] == 0
    assert candidate["production_eligible"] is False
    assert report["shadow_ready"] is True
    assert report["routing_ready"] is False
    assert report["recommended_model"] == "default"


def test_shadow_qualified_candidate_becomes_production_eligible_after_live_gate():
    rows = [
        *[record("default", 0.90, "live") for _ in range(12)],
        *[record("candidate", 0.96, "shadow", cost=0.002) for _ in range(10)],
        *[record("candidate", 0.95, "live", cost=0.002) for _ in range(3)],
    ]
    report = _score_with_evidence_gates(
        rows,
        candidates=["default", "candidate"],
        default_model="default",
        min_samples=10,
        min_live_samples=3,
        quality_floor=0.84,
    )
    candidate = next(row for row in report["candidates"] if row["model"] == "candidate")
    assert candidate["production_eligible"] is True
    assert candidate["live_samples"] == 3
    assert report["routing_ready"] is True


def test_step_parser_keeps_shadow_evidence_separate_from_live_performance():
    content_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step = SimpleNamespace(
        model="default",
        output_json={
            "_provider_meta": {"model": "default", "latency_ms": 400, "estimated_cost_usd": 0.01},
            "_model_router_shadow": {
                "candidate_model": "candidate",
                "production_quality": 0.91,
                "candidate_quality": 0.95,
                "candidate_provider_meta": {"model": "candidate", "latency_ms": 250, "estimated_cost_usd": 0.002},
            },
        },
    )
    run = SimpleNamespace(id=run_id, quality_score=0.89, content_item_id=content_id)
    rows = records_from_step(step, run, {run_id: 0.7})
    live = next(row for row in rows if row["evidence_source"] == "live")
    shadow = next(row for row in rows if row["evidence_source"] == "shadow")
    assert live["model"] == "default"
    assert live["quality"] == 0.91
    assert live["performance"] == 0.7
    assert shadow["model"] == "candidate"
    assert shadow["quality"] == 0.95
    assert shadow["performance"] is None
