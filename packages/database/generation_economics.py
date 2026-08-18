"""Aggregate provider telemetry persisted in GenerationStep outputs.

Provider prices are deliberately not embedded here. Workers record usage/latency and,
when operators configure pricing rates, a known estimated cost. Unknown cost remains
explicitly unknown instead of being guessed from stale vendor pricing.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def extract_provider_meta(value: Any) -> list[dict[str, Any]]:
    """Recursively find telemetry emitted by provider adapters.

    Recursion is intentional: media stages can contain several vision-review attempts,
    each of which is a real provider request and should be counted independently.
    """
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        meta = value.get("_provider_meta")
        if isinstance(meta, dict):
            result.append(meta)
        for key, child in value.items():
            if key == "_provider_meta":
                continue
            result.extend(extract_provider_meta(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(extract_provider_meta(child))
    return result


def _empty_bucket() -> dict[str, Any]:
    return {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "latency_ms_total": 0,
        "latency_samples": 0,
        "known_cost_usd": 0.0,
        "priced_requests": 0,
        "unpriced_requests": 0,
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _add(bucket: dict[str, Any], meta: dict[str, Any]) -> None:
    bucket["requests"] += 1
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = _number(meta.get(key))
        if value is not None:
            bucket[key] += int(value)
    latency = _number(meta.get("latency_ms"))
    if latency is not None:
        bucket["latency_ms_total"] += int(latency)
        bucket["latency_samples"] += 1
    cost = _number(meta.get("estimated_cost_usd"))
    if cost is None:
        bucket["unpriced_requests"] += 1
    else:
        bucket["known_cost_usd"] += cost
        bucket["priced_requests"] += 1


def _clean(bucket: dict[str, Any]) -> dict[str, Any]:
    samples = int(bucket["latency_samples"])
    return {
        "requests": int(bucket["requests"]),
        "input_tokens": int(bucket["input_tokens"]),
        "output_tokens": int(bucket["output_tokens"]),
        "total_tokens": int(bucket["total_tokens"]),
        "average_latency_ms": round(bucket["latency_ms_total"] / samples) if samples else None,
        "known_cost_usd": round(float(bucket["known_cost_usd"]), 6),
        "priced_requests": int(bucket["priced_requests"]),
        "unpriced_requests": int(bucket["unpriced_requests"]),
    }


def aggregate_generation_economics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    total = _empty_bucket()
    by_stage: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    by_model: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    by_provider: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    traced_steps = 0

    for record in records:
        metas = extract_provider_meta(record.get("output_json") or {})
        if metas:
            traced_steps += 1
        stage = str(record.get("stage") or "unknown")
        for meta in metas:
            provider = str(meta.get("provider") or record.get("provider") or "unknown")
            model = str(meta.get("model") or record.get("model") or "unknown")
            _add(total, meta)
            _add(by_stage[stage], meta)
            _add(by_model[model], meta)
            _add(by_provider[provider], meta)

    clean_total = _clean(total)
    return {
        **clean_total,
        "traced_steps": traced_steps,
        "pricing_complete": clean_total["requests"] > 0 and clean_total["unpriced_requests"] == 0,
        "pricing_configured_for_any": clean_total["priced_requests"] > 0,
        "by_stage": {key: _clean(value) for key, value in sorted(by_stage.items())},
        "by_model": {key: _clean(value) for key, value in sorted(by_model.items())},
        "by_provider": {key: _clean(value) for key, value in sorted(by_provider.items())},
    }
