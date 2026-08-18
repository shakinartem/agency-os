from database.model_router_outcomes import apply_outcome_gates


def base_report(performance_samples: int, live_samples: int = 3):
    return {
        "minimum_live_samples": 3,
        "stages": {
            "draft": {
                "candidates": [
                    {"model": "default", "eligible": True, "score": 0.90, "live_samples": 20, "performance_samples": 20},
                    {"model": "candidate", "eligible": True, "score": 0.95, "live_samples": live_samples, "performance_samples": performance_samples},
                ]
            },
            "batch_plan": {
                "candidates": [
                    {"model": "default", "eligible": True, "score": 0.90, "live_samples": 20, "performance_samples": 0},
                    {"model": "candidate", "eligible": True, "score": 0.95, "live_samples": live_samples, "performance_samples": 0},
                ]
            },
        },
    }


def test_content_stage_requires_real_downstream_samples_before_full_switch():
    report = apply_outcome_gates(base_report(performance_samples=0), default_model="default", minimum_downstream_samples=3)
    draft = report["stages"]["draft"]
    candidate = draft["candidates"][1]
    assert candidate["production_eligible"] is False
    assert candidate["downstream_gate_passed"] is False
    assert draft["recommended_model"] == "default"
    assert draft["routing_ready"] is False


def test_content_stage_can_switch_after_downstream_gate():
    report = apply_outcome_gates(base_report(performance_samples=3), default_model="default", minimum_downstream_samples=3)
    draft = report["stages"]["draft"]
    candidate = draft["candidates"][1]
    assert candidate["production_eligible"] is True
    assert draft["routing_ready"] is True
    assert draft["recommended_model"] == "candidate"


def test_strategy_stage_does_not_fake_direct_downstream_attribution():
    report = apply_outcome_gates(base_report(performance_samples=0), default_model="default", minimum_downstream_samples=3)
    batch = report["stages"]["batch_plan"]
    candidate = batch["candidates"][1]
    assert candidate["requires_downstream_outcomes"] is False
    assert candidate["production_eligible"] is True
    assert batch["recommended_model"] == "candidate"
