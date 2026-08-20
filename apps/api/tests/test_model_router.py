import uuid

from database.model_router import (
    choose_from_stage_report,
    deterministic_fraction,
    score_stage_candidates,
    stage_family,
)


def rows(model: str, quality: float, *, count: int, cost: float | None, latency: int, performance: float | None = None):
    return [
        {
            "model": model,
            "quality": quality,
            "performance": performance,
            "latency_ms": latency,
            "cost_usd": cost,
        }
        for _ in range(count)
    ]


def test_stage_family_collapses_sparse_platform_and_strategy_stages():
    assert stage_family("adapt:telegram") == "adapt"
    assert stage_family("adapt:vk:human_approved") == "adapt"
    assert stage_family("final_evaluate") == "evaluate"
    assert stage_family("batch_revise_plan") == "batch_plan"
    assert stage_family("rubric_generate") == "strategy_write"
    assert stage_family("rubric_recheck") == "strategy_review"
    assert stage_family("research") is None


def test_cheap_model_cannot_win_if_it_fails_quality_floor():
    records = [
        *rows("strong", 0.93, count=10, cost=0.02, latency=900, performance=0.65),
        *rows("cheap-bad", 0.70, count=10, cost=0.0001, latency=120, performance=0.70),
    ]
    report = score_stage_candidates(
        records,
        candidates=["strong", "cheap-bad"],
        default_model="strong",
        min_samples=10,
        quality_floor=0.84,
    )
    bad = next(row for row in report["candidates"] if row["model"] == "cheap-bad")
    assert bad["eligible"] is False
    assert bad["score"] is None
    assert report["recommended_model"] == "strong"
    assert report["routing_ready"] is False


def test_missing_price_is_not_treated_as_free():
    records = [
        *rows("priced", 0.92, count=10, cost=0.01, latency=500),
        *rows("unpriced", 0.92, count=10, cost=None, latency=500),
    ]
    report = score_stage_candidates(
        records,
        candidates=["priced", "unpriced"],
        default_model="priced",
        min_samples=10,
        quality_floor=0.84,
    )
    unpriced = next(row for row in report["candidates"] if row["model"] == "unpriced")
    assert unpriced["average_cost_usd"] is None
    assert unpriced["priced_samples"] == 0
    assert unpriced["eligible"] is True
    assert unpriced["score"] is not None


def test_shadow_mode_never_changes_production_model():
    report = {
        "recommended_model": "candidate-b",
        "routing_ready": True,
        "candidate_count": 2,
        "eligible_count": 2,
        "candidates": [
            {"model": "default", "samples": 20},
            {"model": "candidate-b", "samples": 20},
        ],
    }
    decision = choose_from_stage_report(
        report,
        run_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        stage="draft",
        default_model="default",
        mode="shadow",
        exploration_rate=0.5,
    )
    assert decision["selected_model"] == "default"
    assert decision["reason"] == "shadow_only"


def test_active_mode_routes_only_when_comparative_evidence_is_ready():
    report = {
        "recommended_model": "candidate-b",
        "routing_ready": True,
        "candidate_count": 2,
        "eligible_count": 2,
        "candidates": [
            {"model": "default", "samples": 20},
            {"model": "candidate-b", "samples": 20},
        ],
    }
    decision = choose_from_stage_report(
        report,
        run_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        stage="evaluate",
        default_model="default",
        mode="active",
        exploration_rate=0.0,
    )
    assert decision["selected_model"] == "candidate-b"
    assert decision["routing_ready"] is True

    not_ready = {**report, "routing_ready": False, "eligible_count": 1}
    fallback = choose_from_stage_report(
        not_ready,
        run_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        stage="evaluate",
        default_model="default",
        mode="active",
        exploration_rate=0.0,
    )
    assert fallback["selected_model"] == "default"
    assert fallback["reason"] == "insufficient_comparative_evidence"


def test_exploration_assignment_is_retry_stable():
    run_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    assert deterministic_fraction(run_id, "draft") == deterministic_fraction(run_id, "draft")
