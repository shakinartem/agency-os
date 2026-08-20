"""Isolated shadow runtime for Prompt × Model experiments.

Loaded after Model Router runtime. Production output always comes from the normal routed control
call. When an active experiment samples the run, one experiment arm is executed in parallel and
judged blindly. Its output is never used downstream. Experiment traces use a separate key so they
cannot contaminate model-only routing evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
from contextvars import ContextVar
from typing import Any

from database.model_router import stage_family
from database.prompt_experiments import (
    resolve_shadow_experiment_assignment,
    stage_prompt_experiment_observation,
)

from . import batch_tasks, factory_worker, model_router_prompt_epoch_runtime, model_router_runtime, review_tasks, strategy_tasks
from . import providers

_EXPERIMENT_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("content_factory_prompt_experiment_context", default=None)
_EXPERIMENT_TRACE: ContextVar[dict[str, Any] | None] = ContextVar("content_factory_prompt_experiment_trace", default=None)

_ORIGINAL_STAGE = model_router_prompt_epoch_runtime.prompt_epoch_stage
_ORIGINAL_CHAT = model_router_runtime.routed_chat_json
_ORIGINAL_COMPLETE = model_router_runtime.routed_complete_step


def _hash_text(*parts: str) -> str:
    raw = "\n\n".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _candidate_inputs(system: str, prompt: str, assignment: dict[str, Any]) -> tuple[str, str]:
    system_append = str(assignment.get("system_append") or "").strip()
    prompt_append = str(assignment.get("prompt_append") or "").strip()
    candidate_system = system
    candidate_prompt = prompt
    if system_append:
        candidate_system += "\n\n[EXPERIMENT CANDIDATE INSTRUCTION]\n" + system_append
    if prompt_append:
        candidate_prompt += "\n\n[EXPERIMENT CANDIDATE INSTRUCTION]\n" + prompt_append
    return candidate_system, candidate_prompt


def _compact_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": assignment.get("experiment_id"),
        "experiment_name": assignment.get("experiment_name"),
        "arm_id": assignment.get("arm_id"),
        "arm_key": assignment.get("arm_key"),
        "arm_name": assignment.get("arm_name"),
        "candidate_model": assignment.get("candidate_model"),
        "control_prompt_version": assignment.get("control_prompt_version"),
        "candidate_prompt_version": assignment.get("candidate_prompt_version"),
        "sample_rate": assignment.get("sample_rate"),
        "primary_metric": assignment.get("primary_metric"),
        "evidence_scope": "prompt_experiment",
    }


async def experiment_stage(
    session,
    run,
    name: str,
    payload: dict[str, Any] | None = None,
    *,
    provider: str = "openai-compatible",
    model: str | None = None,
):
    _EXPERIMENT_CONTEXT.set(None)
    _EXPERIMENT_TRACE.set(None)
    step = await _ORIGINAL_STAGE(
        session,
        run,
        name,
        payload,
        provider=provider,
        model=model,
    )
    if provider != "openai-compatible":
        return step

    family = stage_family(name)
    assignment = await resolve_shadow_experiment_assignment(session, run, family)
    if not assignment:
        return step

    assignment = dict(assignment)
    assignment["stage_family"] = family
    context = {
        "assignment": assignment,
        "run": run,
        "step": step,
        "consumed": False,
        "control_model": step.model or providers.LLM_MODEL,
    }
    _EXPERIMENT_CONTEXT.set(context)
    input_json = dict(step.input_json or {})
    input_json["_prompt_experiment"] = _compact_assignment(assignment)
    step.input_json = input_json
    await session.flush()
    return step


async def experiment_chat_json(system: str, prompt: str, *, model: str | None = None) -> dict[str, Any]:
    context = _EXPERIMENT_CONTEXT.get()
    if not context:
        return await _ORIGINAL_CHAT(system, prompt, model=model)

    if context.get("consumed"):
        selected_model = model or model_router_runtime._ROUTED_MODEL.get() or providers.LLM_MODEL
        return await model_router_runtime._call_model(system, prompt, selected_model)

    context["consumed"] = True
    assignment = context["assignment"]
    selected_model = model or model_router_runtime._ROUTED_MODEL.get() or providers.LLM_MODEL
    candidate_model = str(assignment.get("candidate_model") or selected_model)
    candidate_system, candidate_prompt = _candidate_inputs(system, prompt, assignment)

    production_call = model_router_runtime._call_model(system, prompt, selected_model)
    candidate_call = model_router_runtime._call_model(candidate_system, candidate_prompt, candidate_model)
    production_result, candidate_result = await asyncio.gather(
        production_call,
        candidate_call,
        return_exceptions=True,
    )

    if isinstance(production_result, BaseException):
        _EXPERIMENT_TRACE.set(None)
        raise production_result

    if isinstance(candidate_result, BaseException):
        trace = {
            "version": "prompt-experiment-shadow/1.0",
            "evidence_scope": "prompt_experiment",
            "status": "candidate_failed",
            "experiment_id": assignment.get("experiment_id"),
            "arm_id": assignment.get("arm_id"),
            "arm_key": assignment.get("arm_key"),
            "candidate_model": candidate_model,
            "control_prompt_version": assignment.get("control_prompt_version"),
            "candidate_prompt_version": assignment.get("candidate_prompt_version"),
            "candidate_prompt_hash": _hash_text(candidate_system, candidate_prompt),
            "production_output_hash": model_router_runtime._payload_hash(production_result),
            "error": str(candidate_result)[:1000],
        }
        _EXPERIMENT_TRACE.set(trace)
        return production_result

    judge_context = dict(model_router_runtime._ROUTER_CONTEXT.get() or {})
    if not judge_context:
        judge_context = {
            "run_id": str(context["run"].id),
            "stage_family": assignment.get("stage_family"),
        }
    trace = await model_router_runtime._judge_shadow_trial(
        system,
        prompt,
        production_result,
        candidate_result,
        judge_context,
        candidate_model,
    )
    trace = {
        **trace,
        "version": "prompt-experiment-shadow/1.0",
        "evidence_scope": "prompt_experiment",
        "experiment_id": assignment.get("experiment_id"),
        "arm_id": assignment.get("arm_id"),
        "arm_key": assignment.get("arm_key"),
        "control_prompt_version": assignment.get("control_prompt_version"),
        "candidate_prompt_version": assignment.get("candidate_prompt_version"),
        "candidate_prompt_hash": _hash_text(candidate_system, candidate_prompt),
        "prompt_delta_hash": _hash_text(
            str(assignment.get("system_append") or ""),
            str(assignment.get("prompt_append") or ""),
        ),
    }
    _EXPERIMENT_TRACE.set(trace)
    return production_result


async def experiment_complete_step(session, step, output: dict[str, Any], status=None) -> None:
    context = _EXPERIMENT_CONTEXT.get()
    trace = _EXPERIMENT_TRACE.get()
    _EXPERIMENT_CONTEXT.set(None)
    _EXPERIMENT_TRACE.set(None)

    persisted = dict(output or {})
    if context and trace:
        persisted["_prompt_experiment_shadow"] = trace
        await stage_prompt_experiment_observation(
            session,
            assignment=context["assignment"],
            trace=trace,
            run=context["run"],
            step=step,
            control_model=str(context.get("control_model") or step.model or providers.LLM_MODEL),
        )

    if status is None:
        await _ORIGINAL_COMPLETE(session, step, persisted)
    else:
        await _ORIGINAL_COMPLETE(session, step, persisted, status=status)


def install() -> None:
    """Install after prompt cohort stamping and model-only shadow routing."""
    for module in (factory_worker, batch_tasks, strategy_tasks, review_tasks):
        module._stage = experiment_stage
        module._complete_step = experiment_complete_step
        module.chat_json = experiment_chat_json


install()
