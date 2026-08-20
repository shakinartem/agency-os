"""Stamp routed GenerationSteps with the explicit evidence prompt cohort.

Loaded after model_router_runtime so every routed stage writes CONTENT_PROMPT_VERSION rather
than relying on a hard-coded worker constant. This keeps model evidence statistically isolated
across prompt deployments without modifying the core pipeline implementation.
"""
from __future__ import annotations

from database.model_router_prompt import current_content_prompt_version

from . import batch_tasks, factory_worker, model_router_runtime, review_tasks, strategy_tasks

_ORIGINAL_ROUTED_STAGE = model_router_runtime.routed_stage


async def prompt_epoch_stage(
    session,
    run,
    name: str,
    payload=None,
    *,
    provider: str = "openai-compatible",
    model: str | None = None,
):
    step = await _ORIGINAL_ROUTED_STAGE(
        session,
        run,
        name,
        payload,
        provider=provider,
        model=model,
    )
    if provider == "openai-compatible":
        step.prompt_version = current_content_prompt_version()
        await session.flush()
    return step


def install() -> None:
    for module in (factory_worker, batch_tasks, strategy_tasks, review_tasks):
        module._stage = prompt_epoch_stage


install()
