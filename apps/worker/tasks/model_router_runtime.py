"""Runtime extension that applies the conservative Model Router without coupling it to the core pipeline.

This module is loaded by Celery after the normal task modules. It wraps the shared stage
function and module-local chat_json references. ContextVar keeps the selected model isolated
between concurrent tasks. Router failures always fail open to the configured default model.
"""
from __future__ import annotations

import json
import os
import time
from contextvars import ContextVar
from typing import Any

import httpx

from database.model_router import choose_model_for_run_stage

from . import batch_tasks, factory_worker, review_tasks, strategy_tasks
from . import providers

_ROUTED_MODEL: ContextVar[str | None] = ContextVar("content_factory_routed_model", default=None)
_ORIGINAL_STAGE = factory_worker._stage


def _model_pricing() -> dict[str, dict[str, float]]:
    try:
        raw = json.loads(os.getenv("LLM_MODEL_PRICING_JSON", "{}") or "{}")
    except json.JSONDecodeError:
        return {}
    result: dict[str, dict[str, float]] = {}
    if not isinstance(raw, dict):
        return result
    for model, rates in raw.items():
        if not isinstance(rates, dict):
            continue
        try:
            input_rate = max(0.0, float(rates.get("input", rates.get("input_per_1m", 0)) or 0))
            output_rate = max(0.0, float(rates.get("output", rates.get("output_per_1m", 0)) or 0))
        except (TypeError, ValueError):
            continue
        if input_rate > 0 or output_rate > 0:
            result[str(model)] = {"input": input_rate, "output": output_rate}
    return result


def _pricing_for_model(model: str, requested_model: str) -> tuple[float, float] | None:
    pricing = _model_pricing()
    for key in (model, requested_model):
        if key in pricing:
            rates = pricing[key]
            return rates["input"], rates["output"]

    default_model = providers.LLM_MODEL
    if model == default_model or requested_model == default_model:
        input_rate = max(0.0, float(os.getenv("LLM_INPUT_COST_PER_1M_USD", "0") or 0))
        output_rate = max(0.0, float(os.getenv("LLM_OUTPUT_COST_PER_1M_USD", "0") or 0))
        if input_rate > 0 or output_rate > 0:
            return input_rate, output_rate
    return None


def provider_usage_meta(data: dict[str, Any], latency_ms: int, requested_model: str) -> dict[str, Any]:
    usage = data.get("usage") or {}
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
        total_tokens = input_tokens + output_tokens

    billed_model = str(data.get("model") or requested_model)
    rates = _pricing_for_model(billed_model, requested_model)
    estimated_cost = None
    if rates is not None and isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
        input_rate, output_rate = rates
        estimated_cost = (
            float(input_tokens) / 1_000_000 * input_rate
            + float(output_tokens) / 1_000_000 * output_rate
        )

    return {
        "provider": "openai-compatible",
        "model": billed_model,
        "requested_model": requested_model,
        "request_id": data.get("id"),
        "input_tokens": int(input_tokens) if isinstance(input_tokens, (int, float)) else None,
        "output_tokens": int(output_tokens) if isinstance(output_tokens, (int, float)) else None,
        "total_tokens": int(total_tokens) if isinstance(total_tokens, (int, float)) else None,
        "latency_ms": latency_ms,
        "estimated_cost_usd": round(estimated_cost, 8) if estimated_cost is not None else None,
        "cost_rates_configured": rates is not None,
    }


async def routed_chat_json(system: str, prompt: str, *, model: str | None = None) -> dict[str, Any]:
    """OpenAI-compatible JSON call using the model selected for the current stage."""
    if not providers.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")

    selected_model = model or _ROUTED_MODEL.get() or providers.LLM_MODEL
    headers = {
        "Authorization": f"Bearer {providers.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{providers.LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    result = providers.parse_json(data["choices"][0]["message"]["content"])
    result["_provider_meta"] = provider_usage_meta(data, latency_ms, selected_model)
    return result


async def routed_stage(
    session,
    run,
    name: str,
    payload: dict[str, Any] | None = None,
    *,
    provider: str = "openai-compatible",
    model: str | None = None,
):
    input_payload = dict(payload or {})
    resolved_model = model

    if provider == "openai-compatible" and resolved_model is None:
        try:
            decision = await choose_model_for_run_stage(
                session,
                run,
                name,
                default_model=providers.LLM_MODEL,
            )
        except Exception as exc:
            decision = {
                "mode": "fallback",
                "stage_family": None,
                "selected_model": providers.LLM_MODEL,
                "recommended_model": providers.LLM_MODEL,
                "reason": "router_error_fail_open",
                "error": str(exc)[:500],
                "routing_ready": False,
                "exploration": False,
            }
        resolved_model = str(decision.get("selected_model") or providers.LLM_MODEL)
        input_payload["_model_router"] = decision
        _ROUTED_MODEL.set(resolved_model)
    elif provider == "openai-compatible":
        resolved_model = resolved_model or providers.LLM_MODEL
        _ROUTED_MODEL.set(resolved_model)
    else:
        _ROUTED_MODEL.set(None)

    return await _ORIGINAL_STAGE(
        session,
        run,
        name,
        input_payload,
        provider=provider,
        model=resolved_model,
    )


def install() -> None:
    """Patch module-local references once after Celery has imported its normal task modules."""
    factory_worker._stage = routed_stage
    factory_worker.chat_json = routed_chat_json

    for module in (batch_tasks, strategy_tasks, review_tasks):
        module._stage = routed_stage
        module.chat_json = routed_chat_json


install()
