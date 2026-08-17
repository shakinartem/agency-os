"""AI strategy and rubric generation tasks."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

from database.base import get_async_session_maker
from database.enums import ContentStatus, ContentType, GenerationRunStatus
from database.models import BrandProfile, ContentItem, ContentVersion, GenerationRun, Rubric

from .factory_worker import _brand_context, _complete_step, _stage
from .providers import chat_json, research_web

RUBRIC_QUALITY_THRESHOLD = 0.82


async def _generate_rubrics(run_id: str) -> None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        run = await session.scalar(select(GenerationRun).where(GenerationRun.id == uuid.UUID(run_id)))
        if not run:
            return
        try:
            run.status = GenerationRunStatus.running
            run.current_stage = "rubric_strategy"
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

            brand_profile = await session.scalar(select(BrandProfile).where(BrandProfile.project_id == run.project_id))
            brand = _brand_context(brand_profile)
            count = min(max(int((run.options or {}).get("rubric_count", 8)), 3), 20)
            goal = (run.options or {}).get("strategy_goal") or run.task

            sources = []
            if (run.options or {}).get("use_research", True):
                research_step = await _stage(session, run, "rubric_research", {"query": goal}, provider="tavily", model=None)
                research = await research_web(goal)
                sources = research.get("sources") or []
                from database.enums import GenerationStepStatus
                research_status = GenerationStepStatus.passed if research.get("status") == "passed" else GenerationStepStatus.skipped
                await _complete_step(session, research_step, research, status=research_status)

            generation_step = await _stage(session, run, "rubric_generate", {"goal": goal, "count": count, "platforms": run.platforms})
            strategy = await chat_json(
                "You are a senior content strategist. Build reusable content systems, not random topic lists. Return JSON only.",
                f"""Create {count} distinct reusable content rubrics for this brand.
Each rubric must have a clear job in the audience journey and generate many future topics without overlapping the others.
Strategy goal: {goal}
Platforms: {run.platforms}
Brand: {json.dumps(brand, ensure_ascii=False)}
Research context: {json.dumps(sources, ensure_ascii=False)}
Return exactly:
{{
  "strategy_summary": "...",
  "rubrics": [
    {{
      "name": "...",
      "description": "...",
      "goal": "...",
      "content_types": ["post", "article"],
      "platforms": ["telegram"],
      "audience_stage": "problem_aware|solution_aware|product_aware|decision|retention",
      "rationale": "why this rubric exists",
      "topic_examples": ["...", "...", "..."],
      "success_metric": "..."
    }}
  ]
}}""",
            )
            await _complete_step(session, generation_step, strategy)

            critic_step = await _stage(session, run, "rubric_critic", {"rubrics": strategy.get("rubrics") or []})
            critic = await chat_json(
                "You are a skeptical head of content strategy. Penalize overlap, generic categories and strategy theater. Return JSON only.",
                f"""Review this rubric system against the brand and goal.
Brand: {json.dumps(brand, ensure_ascii=False)}
Goal: {goal}
Rubrics: {json.dumps(strategy, ensure_ascii=False)}
Return exactly {{"overall":0.0,"brand_fit":0.0,"coverage":0.0,"distinctness":0.0,"actionability":0.0,"notes":[]}}.""",
            )
            await _complete_step(session, critic_step, critic)

            overall = float(critic.get("overall", 0))
            distinctness = float(critic.get("distinctness", 0))
            if overall < RUBRIC_QUALITY_THRESHOLD or distinctness < 0.80:
                revision_step = await _stage(session, run, "rubric_revise", {"review": critic})
                strategy = await chat_json(
                    "You are a senior content strategist revising a weak rubric system. Return JSON only.",
                    f"""Fix the strategy using the critic notes. Remove overlapping/generic rubrics and improve audience-journey coverage.
Brand: {json.dumps(brand, ensure_ascii=False)}
Goal: {goal}
Current strategy: {json.dumps(strategy, ensure_ascii=False)}
Critic: {json.dumps(critic, ensure_ascii=False)}
Keep the same JSON schema and target {count} rubrics.""",
                )
                await _complete_step(session, revision_step, strategy)

                recheck_step = await _stage(session, run, "rubric_recheck")
                critic = await chat_json(
                    "You are a skeptical head of content strategy. Return JSON only.",
                    f"""Re-score the revised strategy. Brand: {json.dumps(brand, ensure_ascii=False)}\nGoal: {goal}\nStrategy: {json.dumps(strategy, ensure_ascii=False)}\nReturn {{"overall":0.0,"brand_fit":0.0,"coverage":0.0,"distinctness":0.0,"actionability":0.0,"notes":[]}}.""",
                )
                await _complete_step(session, recheck_step, critic)
                overall = float(critic.get("overall", 0))
                distinctness = float(critic.get("distinctness", 0))

            rubric_rows = (strategy.get("rubrics") or [])[:count]
            strategy_item = ContentItem(
                project_id=run.project_id,
                type=ContentType.rubric,
                status=ContentStatus.ready if overall >= RUBRIC_QUALITY_THRESHOLD and distinctness >= 0.80 else ContentStatus.review,
                title=f"Content rubric strategy: {goal[:180]}",
                body=strategy.get("strategy_summary") or "",
                task=run.task,
                topic="Content strategy and rubrics",
                goal=goal,
                platforms=run.platforms,
                structured_json={**strategy, "critic": critic},
                research_sources=sources,
                quality_score=overall,
                current_version=1,
            )
            session.add(strategy_item)
            await session.flush()
            session.add(ContentVersion(
                content_item_id=strategy_item.id,
                run_id=run.id,
                version=1,
                stage="rubric_strategy",
                title=strategy_item.title,
                body=strategy_item.body,
                structured_json=strategy_item.structured_json,
            ))
            run.content_item_id = strategy_item.id
            run.quality_score = overall

            if strategy_item.status == ContentStatus.ready:
                # Keep historical AI rubrics for learning, but only the latest generated strategy stays active.
                await session.execute(
                    update(Rubric)
                    .where(Rubric.project_id == run.project_id, Rubric.origin == "ai", Rubric.active.is_(True))
                    .values(active=False)
                )
                for rubric in rubric_rows:
                    name = str(rubric.get("name") or "").strip()
                    if not name:
                        continue
                    session.add(Rubric(
                        project_id=run.project_id,
                        generation_run_id=run.id,
                        name=name[:255],
                        description=rubric.get("description"),
                        goal=str(rubric.get("goal") or "")[:255] or None,
                        content_types=rubric.get("content_types") or [],
                        platforms=rubric.get("platforms") or run.platforms or [],
                        origin="ai",
                        metadata_json={
                            "audience_stage": rubric.get("audience_stage"),
                            "rationale": rubric.get("rationale"),
                            "topic_examples": rubric.get("topic_examples") or [],
                            "success_metric": rubric.get("success_metric"),
                            "critic": critic,
                        },
                        active=True,
                    ))
                run.status = GenerationRunStatus.ready
                run.current_stage = "rubrics_ready"
            else:
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "rubric_strategy_review"

            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            run = await session.scalar(select(GenerationRun).where(GenerationRun.id == uuid.UUID(run_id)))
            if run:
                run.status = GenerationRunStatus.failed
                run.error = str(exc)[:4000]
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
            raise


@shared_task(name="content_factory.generate_rubrics")
def generate_rubrics(run_id: str) -> None:
    asyncio.run(_generate_rubrics(run_id))
