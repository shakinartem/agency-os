"""Runtime extension that applies the conservative Model Router without coupling it to the core pipeline.

Shadow mode can collect prompt-level evidence for under-sampled candidates without changing
user-visible production output. Candidate output is never used downstream. Only compact
hashes, judge scores and provider telemetry are persisted in GenerationStep traces.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextvars import ContextVar
from typing import Any

import httpx

from database.model_router import deterministic_fraction
from database.model_router_active import choose_model_for_run_stage

from . import batch_tasks, factory_worker, review_tasks, strategy_tasks
from . import providers

_ROUTED_MODEL: ContextVar[str | None] = ContextVar("content_factory_routed_model", default=None)
_ROUTER_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("content_factory_router_context", default=None)
_SHADOW_TRACE: ContextVar[dict[str, Any] | None] = ContextVar("content_factory_shadow_trace", default=None)
_ORIGINAL_STAGE = factory_worker._stage
_ORIGINAL_COMPLETE_STEP = factory_worker._complete_step


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


def _without_internal(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_internal(child)
            for key, child in value.items()
            if key not in {"_provider_meta", "_model_router_shadow"}
        }
    if isinstance(value, list):
        return [_without_internal(child) for child in value]
    return value


def _payload_hash(value: Any) -> str:
    raw = json.dumps(_without_internal(value), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _call_model(system: str, prompt: str, model: str) -> dict[str, Any]:
    if not providers.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")
    headers = {
        "Authorization": f"Bearer {providers.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
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
    result["_provider_meta"] = provider_usage_meta(data, latency_ms, model)
    return result


def _shadow_candidate(decision: dict[str, Any], default_model: str) -> str | None:
    evidence = decision.get("evidence") or {}
    candidates = [row for row in (evidence.get("candidates") or []) if isinstance(row, dict)]
    candidates = [row for row in candidates if str(row.get("model") or "") and str(row.get("model")) != default_model]
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            int(row.get("samples") or 0),
            int(row.get("live_samples") or 0),
            str(row.get("model") or ""),
        )
    )
    return str(candidates[0]["model"])


def _should_shadow_trial(context: dict[str, Any] | None, candidate_model: str | None) -> bool:
    if not context or not candidate_model:
        return False
    decision = context.get("decision") or {}
    if decision.get("mode") != "shadow":
        return False
    if context.get("already_sampled"):
        return False
    rate = min(0.5, max(0.0, float(decision.get("shadow_sample_rate") or os.getenv("MODEL_ROUTER_SHADOW_SAMPLE_RATE", "0.05"))))
    if rate <= 0:
        return False
    run_id = context.get("run_id")
    family = context.get("stage_family")
    if not run_id or not family:
        return False
    return deterministic_fraction(run_id, f"{family}:shadow") < rate


def _mark_shadow_sampled(context: dict[str, Any]) -> None:
    run = context.get("run")
    family = context.get("stage_family")
    if run is None or not family:
        return
    options = dict(run.options or {})
    sampled = list(options.get("_model_router_shadow_sampled") or [])
    if family not in sampled:
        sampled.append(family)
    options["_model_router_shadow_sampled"] = sampled
    run.options = options
    context["already_sampled"] = True


async def _run_shadow_trial(
    system: str,
    prompt: str,
    production_result: dict[str, Any],
    context: dict[str, Any],
    candidate_model: str,
) -> dict[str, Any]:
    _mark_shadow_sampled(context)
    try:
        candidate_result = await _call_model(system, prompt, candidate_model)
    except Exception as exc:
        return {
            "version": "shadow-trial/1.0",
            "status": "candidate_failed",
            "candidate_model": candidate_model,
            "error": str(exc)[:1000],
        }

    candidate_meta = candidate_result.get("_provider_meta") if isinstance(candidate_result.get("_provider_meta"), dict) else {}
    judge_model = os.getenv("MODEL_ROUTER_JUDGE_MODEL", "").strip() or providers.LLM_MODEL
    judge_prompt = (
        "Compare two candidate JSON responses to the same production prompt. Score each 0..1 for instruction adherence, "
        "factual restraint, usefulness, clarity and format correctness. Do not reward verbosity. The production response "
        "is the control; the candidate is experimental. Return JSON only with exactly: "
        '{"production_quality":0.0,"candidate_quality":0.0,"winner":"production|candidate|tie","notes":[]}.'
        f"\nOriginal system instruction: {system}"
        f"\nOriginal user prompt: {prompt}"
        f"\nProduction response: {json.dumps(_without_internal(production_result), ensure_ascii=False)}"
        f"\nCandidate response: {json.dumps(_without_internal(candidate_result), ensure_ascii=False)}"
    )
    try:
        judged = await _call_model(
            "You are an independent strict evaluator for an offline model-routing experiment. Return JSON only.",
            judge_prompt,
            judge_model,
        )
    except Exception as exc:
        return {
            "version": "shadow-trial/1.0",
            "status": "judge_failed",
            "candidate_model": candidate_model,
            "candidate_provider_meta": candidate_meta,
            "provider_traces": [{"role": "candidate", "_provider_meta": candidate_meta}],
            "production_output_hash": _payload_hash(production_result),
            "candidate_output_hash": _payload_hash(candidate_result),
            "error": str(exc)[:1000],
        }

    judge_meta = judged.get("_provider_meta") if isinstance(judged.get("_provider_meta"), dict) else {}
    production_quality = judged.get("production_quality")
    candidate_quality = judged.get("candidate_quality")
    valid_scores = all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (production_quality, candidate_quality))
    return {
        "version": "shadow-trial/1.0",
        "status": "passed" if valid_scores else "invalid_judge_scores",
        "candidate_model": candidate_model,
        "judge_model": judge_model,
        "production_quality": float(production_quality) if valid_scores else None,
        "candidate_quality": float(candidate_quality) if valid_scores else None,
        "winner": judged.get("winner"),
        "notes": (judged.get("notes") or [])[:10] if isinstance(judged.get("notes"), list) else [],
        "candidate_provider_meta": candidate_meta,
        "judge_provider_meta": judge_meta,
        "provider_traces": [
            {"role": "candidate", "_provider_meta": candidate_meta},
            {"role": "judge", "_provider_meta": judge_meta},
        ],
        "production_output_hash": _payload_hash(production_result),
        "candidate_output_hash": _payload_hash(candidate_result),
    }


async def routed_chat_json(system: str, prompt: str, *, model: str | None = None) -> dict[str, Any]:
    """Return production output while optionally collecting an isolated shadow candidate trial."""
    selected_model = model or _ROUTED_MODEL.get() or providers.LLM_MODEL
    production_result = await _call_model(system, prompt, selected_model)

    context = _ROUTER_CONTEXT.get()
    candidate_model = _shadow_candidate((context or {}).get("decision") or {}, providers.LLM_MODEL)
    if _should_shadow_trial(context, candidate_model):
        trace = await _run_shadow_trial(system, prompt, production_result, context or {}, candidate_model or "")
        _SHADOW_TRACE.set(trace)
    else:
        _SHADOW_TRACE.set(None)
    return production_result


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
    _SHADOW_TRACE.set(None)

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
                "shadow_sample_rate": 0.0,
                "evidence": {"candidates": []},
            }
        resolved_model = str(decision.get("selected_model") or providers.LLM_MODEL)
        input_payload["_model_router"] = decision
        _ROUTED_MODEL.set(resolved_model)
        sampled = set((run.options or {}).get("_model_router_shadow_sampled") or [])
        _ROUTER_CONTEXT.set({
            "run": run,
            "run_id": str(run.id),
            "stage_family": decision.get("stage_family"),
            "decision": decision,
            "already_sampled": decision.get("stage_family") in sampled,
        })
    elif provider == "openai-compatible":
        resolved_model = resolved_model or providers.LLM_MODEL
        _ROUTED_MODEL.set(resolved_model)
        _ROUTER_CONTEXT.set(None)
    else:
        _ROUTED_MODEL.set(None)
        _ROUTER_CONTEXT.set(None)

    return await _ORIGINAL_STAGE(
        session,
        run,
        name,
        input_payload,
        provider=provider,
        model=resolved_model,
    )


async def routed_complete_step(session, step, output: dict[str, Any], status=None) -> None:
    trace = _SHADOW_TRACE.get()
    _SHADOW_TRACE.set(None)
    persisted = dict(output or {})
    if trace:
        persisted["_model_router_shadow"] = trace
    if status is None:
        await _ORIGINAL_COMPLETE_STEP(session, step, persisted)
    else:
        await _ORIGINAL_COMPLETE_STEP(session, step, persisted, status=status)


def install() -> None:
    """Patch module-local references once after Celery has imported its normal task modules."""
    factory_worker._stage = routed_stage
    factory_worker._complete_step = routed_complete_step
    factory_worker.chat_json = routed_chat_json

    for module in (batch_tasks, strategy_tasks, review_tasks):
        module._stage = routed_stage
        module._complete_step = routed_complete_step
        module.chat_json = routed_chat_json


install()
