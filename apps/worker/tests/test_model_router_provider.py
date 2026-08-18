from apps.worker.tasks import providers


def test_model_specific_pricing_is_used_for_routed_model(monkeypatch):
    monkeypatch.setattr(providers, "LLM_MODEL_PRICING_JSON", '{"candidate":{"input":2.0,"output":8.0}}')
    monkeypatch.setattr(providers, "LLM_INPUT_COST_PER_1M_USD", 0.0)
    monkeypatch.setattr(providers, "LLM_OUTPUT_COST_PER_1M_USD", 0.0)
    meta = providers._provider_usage_meta(
        {"model": "candidate", "usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        250,
        "candidate",
    )
    assert meta["cost_rates_configured"] is True
    assert meta["estimated_cost_usd"] == 0.006
    assert meta["requested_model"] == "candidate"


def test_unknown_candidate_price_stays_unknown(monkeypatch):
    monkeypatch.setattr(providers, "LLM_MODEL_PRICING_JSON", "{}")
    monkeypatch.setattr(providers, "LLM_INPUT_COST_PER_1M_USD", 1.0)
    monkeypatch.setattr(providers, "LLM_OUTPUT_COST_PER_1M_USD", 2.0)
    monkeypatch.setattr(providers, "LLM_MODEL", "default")
    meta = providers._provider_usage_meta(
        {"model": "other", "usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
        250,
        "other",
    )
    assert meta["cost_rates_configured"] is False
    assert meta["estimated_cost_usd"] is None
