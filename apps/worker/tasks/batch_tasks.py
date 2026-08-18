"""Production batch planning and child-run fan-out."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from database.base import get_async_session_maker
from database.enums import GenerationRunStatus
from database.models import BrandProfile, GenerationRun, ProductionBatch, ProductionBatchItem, Rubric
from database.performance_learning import build_performance_learning_context
from database.task_outbox import enqueue_task

from .batch_prompts import generation_prompt, revision_prompt
from .batch_validation import validate_batch_plan
from .factory_worker import _brand_context, _complete_step, _stage, app
from .knowledge import retrieve_knowledge
from .providers import chat_json, research_web

MAX_BATCH_ITEMS = 100


def _compact_learning_snapshot(context: dict) -> dict:
    return {
        "status": context.get("status"),
        "publications": context.get("publications", 0),
        "primary_metric": context.get("primary_metric"),
        "baseline": context.get("baseline"),
        "exploration_share": context.get("exploration_share"),
        "recommendations": context.get("recommendations") or {},
    }


async def _plan_batch(batch_id: str) -> None:
    maker = get_async_session_maker()
    async with maker() as session:
        batch = await session.scalar(select(ProductionBatch).where(ProductionBatch.id == uuid.UUID(batch_id)))
        if not batch:
            return
        planner_run = await session.scalar(select(GenerationRun).where(GenerationRun.id == batch.planner_run_id)) if batch.planner_run_id else None
        if planner_run is None:
            batch.status = "failed"
            batch.error = "Planner run not found"
            await session.commit()
            return
        if batch.status in {"production", "completed"}:
            return

        try:
            batch.status = "planning"
            planner_run.status = GenerationRunStatus.running
            planner_run.current_stage = "batch_plan"
            planner_run.started_at = datetime.now(timezone.utc)
            await session.commit()

            content_mix = {str(key).strip().lower(): int(value) for key, value in (batch.content_mix or {}).items() if int(value) > 0}
            if not content_mix or sum(content_mix.values()) > MAX_BATCH_ITEMS:
                raise ValueError("Invalid content_mix")

            brand_profile = await session.scalar(select(BrandProfile).where(BrandProfile.project_id == batch.project_id))
            brand = _brand_context(brand_profile)
            rubric_rows = (await session.execute(select(Rubric).where(Rubric.project_id == batch.project_id, Rubric.active.is_(True)))).scalars().all()
            rubrics = [
                {"id": str(row.id), "name": row.name, "description": row.description, "goal": row.goal, "content_types": row.content_types or [], "platforms": row.platforms or [], "metadata": row.metadata_json or {}}
                for row in rubric_rows
            ]
            allowed_rubric_ids = {row["id"] for row in rubrics}
            knowledge = await retrieve_knowledge(session, batch.project_id, batch.objective, limit=8) if (batch.options or {}).get("use_knowledge", True) else []
            research_sources = []
            if (batch.options or {}).get("use_research", True):
                research_sources = (await research_web(batch.objective)).get("sources") or []

            use_performance = (batch.options or {}).get("use_performance_learning", True)
            performance = (
                await build_performance_learning_context(session, batch.project_id)
                if use_performance
                else {
                    "status": "disabled",
                    "publications": 0,
                    "primary_metric": None,
                    "baseline": 0,
                    "exploration_share": 0.25,
                    "recommendations": {"winners": [], "watch": [], "guidance": ["Performance learning disabled for this batch."]},
                }
            )
            learning_snapshot = _compact_learning_snapshot(performance)
            batch.options = {**(batch.options or {}), "performance_learning_snapshot": learning_snapshot}

            step = await _stage(session, planner_run, "batch_generate_plan", {
                "objective": batch.objective,
                "content_mix": content_mix,
                "platforms": batch.platforms,
                "rubric_count": len(rubrics),
                "performance_status": performance.get("status"),
                "performance_publications": performance.get("publications", 0),
                "performance_primary_metric": performance.get("primary_metric"),
            })
            plan = await chat_json(
                "You are a senior content portfolio strategist. Return JSON only. Build a production series, not a random list.",
                generation_prompt(
                    objective=batch.objective,
                    platforms=batch.platforms or [],
                    content_mix=content_mix,
                    brand=brand,
                    rubrics=rubrics,
                    knowledge=knowledge,
                    research=research_sources,
                    performance=performance,
                ),
            )
            await _complete_step(session, step, plan)
            items = plan.get("items") or []
            errors = validate_batch_plan(items, content_mix, allowed_rubric_ids)

            if errors:
                revise_step = await _stage(session, planner_run, "batch_revise_plan", {"errors": errors})
                plan = await chat_json(
                    "You are revising a content portfolio plan that failed deterministic validation. Return JSON only.",
                    revision_prompt(objective=batch.objective, content_mix=content_mix, rubrics=rubrics, errors=errors, plan=plan),
                )
                await _complete_step(session, revise_step, plan)
                items = plan.get("items") or []
                errors = validate_batch_plan(items, content_mix, allowed_rubric_ids)

            if errors:
                batch.status = "review"
                batch.error = "; ".join(errors)[:4000]
                batch.strategy_summary = plan.get("strategy_summary")
                planner_run.status = GenerationRunStatus.awaiting_review
                planner_run.current_stage = "batch_plan_review"
                planner_run.error = batch.error
                planner_run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return

            batch.strategy_summary = plan.get("strategy_summary")
            batch.status = "production"
            for position, spec in enumerate(items, start=1):
                rubric_id = spec.get("rubric_id")
                learning_mode = str(spec.get("learning_mode") or "explore").lower()
                if learning_mode not in {"exploit", "explore"}:
                    learning_mode = "explore"
                child_run = GenerationRun(
                    project_id=batch.project_id,
                    task=(
                        f"Create this planned content item.\n"
                        f"Batch objective: {batch.objective}\n"
                        f"Topic: {spec.get('topic')}\n"
                        f"Goal: {spec.get('goal') or ''}\n"
                        f"Angle: {spec.get('angle') or ''}\n"
                        f"Audience stage: {spec.get('audience_stage') or ''}\n"
                        f"Learning mode: {learning_mode}\n"
                        f"Brief: {spec.get('brief') or ''}"
                    ),
                    content_type=str(spec.get("content_type") or "post").lower(),
                    platforms=batch.platforms or ["telegram"],
                    options={
                        **(batch.options or {}),
                        "batch_id": str(batch.id),
                        "batch_position": position,
                        "rubric_id": rubric_id,
                        "planned_topic": spec.get("topic"),
                        "learning_mode": learning_mode,
                    },
                )
                session.add(child_run)
                await session.flush()
                session.add(ProductionBatchItem(
                    batch_id=batch.id,
                    rubric_id=(uuid.UUID(rubric_id) if rubric_id else None),
                    child_run_id=child_run.id,
                    position=position,
                    content_type=child_run.content_type,
                    topic=str(spec.get("topic") or "")[:500],
                    goal=(str(spec.get("goal"))[:255] if spec.get("goal") else None),
                    status="queued",
                    metadata_json={
                        "angle": spec.get("angle"),
                        "audience_stage": spec.get("audience_stage"),
                        "brief": spec.get("brief"),
                        "learning_mode": learning_mode,
                        "performance_primary_metric": performance.get("primary_metric"),
                    },
                ))
                await enqueue_task(session, "content_factory.process_run", args=[str(child_run.id)], dedupe_key=f"run:{child_run.id}:process")

            planner_run.status = GenerationRunStatus.ready
            planner_run.current_stage = "batch_fanned_out"
            planner_run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            try:
                app.send_task("content_factory.dispatch_task_outbox")
            except Exception:
                pass
        except Exception as exc:
            await session.rollback()
            batch = await session.scalar(select(ProductionBatch).where(ProductionBatch.id == uuid.UUID(batch_id)))
            planner_run = await session.scalar(select(GenerationRun).where(GenerationRun.id == batch.planner_run_id)) if batch and batch.planner_run_id else None
            if batch:
                batch.status = "failed"
                batch.error = str(exc)[:4000]
            if planner_run:
                planner_run.status = GenerationRunStatus.failed
                planner_run.error = str(exc)[:4000]
                planner_run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            raise


@shared_task(name="content_factory.plan_batch")
def plan_batch(batch_id: str) -> None:
    asyncio.run(_plan_batch(batch_id))
