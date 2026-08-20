from types import SimpleNamespace
import uuid

from database.model_router_evidence import records_from_step


def test_prompt_experiment_candidate_trace_is_not_model_router_evidence():
    content_id = uuid.uuid4()
    run_id = uuid.uuid4()
    run = SimpleNamespace(id=run_id, content_item_id=content_id, quality_score=0.88)
    step = SimpleNamespace(
        model="control-model",
        output_json={
            "_provider_meta": {"model": "control-model", "latency_ms": 1000, "estimated_cost_usd": 0.01},
            "_prompt_experiment_shadow": {
                "candidate_model": "candidate-model",
                "candidate_quality": 0.99,
                "candidate_provider_meta": {"model": "candidate-model", "latency_ms": 500, "estimated_cost_usd": 0.001},
            },
        },
    )
    rows = records_from_step(step, run, {run_id: 0.7})
    assert [row["model"] for row in rows] == ["control-model"]
    assert rows[0]["performance"] == 0.7
