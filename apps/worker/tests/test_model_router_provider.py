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
