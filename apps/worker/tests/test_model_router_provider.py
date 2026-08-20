from apps.worker.tasks import model_router_runtime
from apps.worker.tasks import providers


def test_model_specific_pricing_is_used_for_routed_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_PRICING_JSON", '{"candidate":{"input":2.0,"output":8.0}}')
    monkeypatch.setenv("LLM_INPUT_COST_PER_1M_USD", "0")
    monkeypatch.setenv("LLM_OUTPUT_COST_PER_1M_USD", "0")
    meta = model_router_runtime.provider_usage_meta(
        {"model": "candidate", "usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        250,
        "candidate",
    )
    assert meta["cost_rates_configured"] is True
    assert meta["estimated_cost_usd"] == 0.006
    assert meta["requested_model"] == "candidate"


def test_unknown_candidate_price_stays_unknown(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_PRICING_JSON", "{}")
    monkeypatch.setenv("LLM_INPUT_COST_PER_1M_USD", "1")
    monkeypatch.setenv("LLM_OUTPUT_COST_PER_1M_USD", "2")
    monkeypatch.setattr(providers, "LLM_MODEL", "default")
    meta = model_router_runtime.provider_usage_meta(
        {"model": "other", "usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        250,
        "other",
    )
    assert meta["cost_rates_configured"] is False
    assert meta["estimated_cost_usd"] is None


def test_shadow_candidate_prefers_least_sampled_non_default():
    decision = {
        "evidence": {
            "candidates": [
                {"model": "default", "samples": 100, "live_samples": 100},
                {"model": "candidate-a", "samples": 8, "live_samples": 0},
                {"model": "candidate-b", "samples": 2, "live_samples": 0},
            ]
        }
    }
    assert model_router_runtime._shadow_candidate(decision, "default") == "candidate-b"


def test_shadow_sampling_is_safe_and_retry_stable(monkeypatch):
    monkeypatch.setattr(model_router_runtime, "deterministic_fraction", lambda *_: 0.01)
    context = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "stage_family": "draft",
        "already_sampled": False,
        "decision": {"mode": "shadow", "shadow_sample_rate": 0.05},
    }
    assert model_router_runtime._should_shadow_trial(context, "candidate") is True
    context["already_sampled"] = True
    assert model_router_runtime._should_shadow_trial(context, "candidate") is False


def test_active_mode_never_runs_offline_shadow_trial(monkeypatch):
    monkeypatch.setattr(model_router_runtime, "deterministic_fraction", lambda *_: 0.0)
    context = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "stage_family": "draft",
        "already_sampled": False,
        "decision": {"mode": "active", "shadow_sample_rate": 0.50},
    }
    assert model_router_runtime._should_shadow_trial(context, "candidate") is False
