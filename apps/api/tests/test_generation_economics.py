from database.generation_economics import aggregate_generation_economics, extract_provider_meta


def meta(*, provider="openai-compatible", model="gpt-test", input_tokens=100, output_tokens=50, latency_ms=200, cost=None):
    return {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": latency_ms,
        "estimated_cost_usd": cost,
    }


def test_recursive_extraction_counts_nested_media_attempts():
    payload = {
        "status": "passed",
        "attempts": [
            {"review": {"overall": 0.7, "_provider_meta": meta(model="vision-a")}},
            {"review": {"overall": 0.95, "_provider_meta": meta(model="vision-b")}},
        ],
    }
    rows = extract_provider_meta(payload)
    assert len(rows) == 2
    assert {row["model"] for row in rows} == {"vision-a", "vision-b"}


def test_economics_never_treats_unknown_price_as_zero_cost():
    result = aggregate_generation_economics([
        {"stage": "draft", "output_json": {"_provider_meta": meta(cost=0.001)}},
        {"stage": "evaluate", "output_json": {"_provider_meta": meta(cost=None)}},
    ])
    assert result["requests"] == 2
    assert result["total_tokens"] == 300
    assert result["known_cost_usd"] == 0.001
    assert result["priced_requests"] == 1
    assert result["unpriced_requests"] == 1
    assert result["pricing_complete"] is False
    assert result["pricing_configured_for_any"] is True


def test_economics_groups_by_stage_model_and_provider():
    result = aggregate_generation_economics([
        {"stage": "draft", "output_json": {"_provider_meta": meta(model="writer", latency_ms=100, cost=0.002)}},
        {"stage": "draft", "output_json": {"_provider_meta": meta(model="writer", latency_ms=300, cost=0.002)}},
        {"stage": "research", "output_json": {"_provider_meta": meta(provider="search", model="search-v1", input_tokens=0, output_tokens=0, latency_ms=50, cost=None)}},
    ])
    assert result["by_stage"]["draft"]["requests"] == 2
    assert result["by_stage"]["draft"]["average_latency_ms"] == 200
    assert result["by_model"]["writer"]["known_cost_usd"] == 0.004
    assert result["by_provider"]["search"]["unpriced_requests"] == 1
