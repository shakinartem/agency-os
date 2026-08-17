"""Production Content Factory worker.

Deterministic pipeline:
research -> draft -> evaluate/revise -> humanize -> adapt -> media/vision QA -> final QA -> package -> optional export.
Every meaningful stage is persisted so failures are diagnosable and retryable.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from sqlalchemy import select

from database.base import get_async_session_maker
from database.enums import (
    ContentStatus,
    ContentType,
    ExportStatus,
    GenerationRunStatus,
    GenerationStepStatus,
    MediaStatus,
)
from database.models import (
    BrandProfile,
    ContentItem,
    ContentVariant,
    ContentVersion,
    Evaluation,
    ExportDelivery,
    GenerationRun,
    GenerationStep,
    MediaAsset,
)

from .content_package import validate_content_package
from .providers import (
    IMAGE_MODEL,
    LLM_MODEL,
    chat_json,
    create_reviewed_media,
    research_web,
    send_to_autoposter,
)

broker_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
app = Celery("content_factory_worker", broker=broker_url)
app.conf.broker_connection_retry_on_startup = True

QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", "0.87"))
FACTUALITY_THRESHOLD = float(os.getenv("FACTUALITY_THRESHOLD", "0.95"))
BRAND_VOICE_THRESHOLD = float(os.getenv("BRAND_VOICE_THRESHOLD", "0.85"))
MAX_REVISIONS = int(os.getenv("MAX_REVISION_ATTEMPTS", "2"))
PROMPT_VERSION = "factory-v2-research-media"


def _brand_context(profile: BrandProfile | None) -> dict[str, Any]:
    if not profile:
        return {"warning": "Brand profile is not configured. Never invent company facts."}
    return {
        "positioning": profile.positioning,
        "audience": profile.audience,
        "products": profile.products,
        "tone_of_voice": profile.tone_of_voice,
        "brand_rules": profile.brand_rules,
        "forbidden_claims": profile.forbidden_claims,
        "examples": profile.examples,
    }


async def _stage(
    session,
    run: GenerationRun,
    name: str,
    payload: dict[str, Any] | None = None,
    *,
    provider: str = "openai-compatible",
    model: str | None = None,
) -> GenerationStep:
    run.current_stage = name
    step = GenerationStep(
        run_id=run.id,
        stage=name,
        status=GenerationStepStatus.running,
        provider=provider,
        model=model if model is not None else (LLM_MODEL if provider == "openai-compatible" else None),
        prompt_version=PROMPT_VERSION,
        input_json=payload or {},
    )
    session.add(step)
    await session.commit()
    return step


async def _complete_step(
    session,
    step: GenerationStep,
    output: dict[str, Any],
    status: GenerationStepStatus = GenerationStepStatus.passed,
) -> None:
    step.output_json = output
    step.status = status
    await session.commit()


async def _save_version(session, item: ContentItem, run: GenerationRun, stage: str, data: dict[str, Any]) -> None:
    item.current_version += 1
    item.title = data.get("title") or data.get("seo_title") or item.title
    item.body = data.get("body") or data.get("script") or item.body
    item.hook = data.get("hook") or data.get("hook_0_3_sec") or item.hook
    item.cta = data.get("cta") or item.cta
    item.hashtags = data.get("hashtags") or item.hashtags
    item.visual_prompt = data.get("visual_prompt") or item.visual_prompt
    item.structured_json = data
    session.add(ContentVersion(
        content_item_id=item.id,
        run_id=run.id,
        version=item.current_version,
        stage=stage,
        title=item.title,
        body=item.body,
        structured_json=data,
    ))
    await session.flush()


def _passes(score: dict[str, Any]) -> bool:
    return (
        float(score.get("overall", 0)) >= QUALITY_THRESHOLD
        and float(score.get("factuality", 0)) >= FACTUALITY_THRESHOLD
        and float(score.get("brand_voice", 0)) >= BRAND_VOICE_THRESHOLD
        and bool(score.get("policy_passed", False))
    )


async def _evaluate(
    session,
    run: GenerationRun,
    item: ContentItem,
    brand: dict[str, Any],
    sources: list[dict[str, Any]],
    stage_name: str = "evaluate",
) -> dict[str, Any]:
    step = await _stage(session, run, stage_name, {"content_item_id": str(item.id), "sources_count": len(sources)})
    result = await chat_json(
        "You are a strict senior content editor and fact-risk reviewer. Return JSON only.",
        f"""Evaluate this content from 0 to 1. Do not reward polished nonsense.
Factuality means externally checkable claims are supported by supplied research sources or brand context; otherwise they must be cautious/general rather than invented.
Brand context: {json.dumps(brand, ensure_ascii=False)}
Research sources: {json.dumps(sources, ensure_ascii=False)}
Content: {json.dumps(item.structured_json or {"title": item.title, "body": item.body}, ensure_ascii=False)}
Return exactly: {{"overall":0.0,"factuality":0.0,"brand_voice":0.0,"clarity":0.0,"hook":0.0,"usefulness":0.0,"originality":0.0,"policy_passed":true,"notes":[]}}""",
    )
    ev = Evaluation(
        content_item_id=item.id,
        run_id=run.id,
        stage=stage_name,
        overall=float(result.get("overall", 0)),
        factuality=float(result.get("factuality", 0)),
        brand_voice=float(result.get("brand_voice", 0)),
        clarity=float(result.get("clarity", 0)),
        hook=float(result.get("hook", 0)),
        usefulness=float(result.get("usefulness", 0)),
        originality=float(result.get("originality", 0)),
        policy_passed=bool(result.get("policy_passed", False)),
        notes=result.get("notes") or [],
        raw_json=result,
    )
    session.add(ev)
    item.quality_score = ev.overall
    run.quality_score = ev.overall
    await _complete_step(session, step, result)
    return result


async def _research(session, run: GenerationRun) -> list[dict[str, Any]]:
    if not (run.options or {}).get("use_research", True):
        return []
    step = await _stage(session, run, "research", {"query": run.task}, provider="tavily", model=None)
    result = await research_web(run.task)
    status = GenerationStepStatus.passed if result.get("status") == "passed" else GenerationStepStatus.skipped
    await _complete_step(session, step, result, status=status)
    return result.get("sources") or []


async def _generate_media(session, run: GenerationRun, item: ContentItem) -> MediaAsset:
    asset = MediaAsset(
        content_item_id=item.id,
        run_id=run.id,
        prompt=item.visual_prompt,
        status=MediaStatus.generating,
        provider="openai-compatible+s3",
        model=IMAGE_MODEL,
    )
    session.add(asset)
    await session.commit()

    if not item.visual_prompt:
        asset.status = MediaStatus.review
        asset.metadata_json = {"reason": "writer did not produce visual_prompt"}
        await session.commit()
        return asset

    step = await _stage(
        session,
        run,
        "media_generate_and_review",
        {"visual_prompt": item.visual_prompt},
        provider="image+vision+s3",
        model=IMAGE_MODEL,
    )
    content_context = json.dumps({"title": item.title, "body": item.body, "goal": item.goal}, ensure_ascii=False)
    result = await create_reviewed_media(item.visual_prompt, content_context, str(item.id))
    asset.metadata_json = {"attempts": result.get("attempts") or [], "reason": result.get("reason")}
    if result.get("status") == "passed":
        asset.url = result.get("url")
        asset.mime_type = result.get("mime_type")
        asset.quality_score = float((result.get("review") or {}).get("overall", 0))
        asset.status = MediaStatus.ready
        await _complete_step(session, step, {k: v for k, v in result.items() if k != "bytes"})
    else:
        asset.status = MediaStatus.review
        await _complete_step(session, step, result, status=GenerationStepStatus.failed)
    await session.commit()
    return asset


async def _package(session, item: ContentItem) -> ExportDelivery:
    variants = (await session.execute(
        select(ContentVariant).where(ContentVariant.content_item_id == item.id)
    )).scalars().all()
    media = (await session.execute(
        select(MediaAsset).where(MediaAsset.content_item_id == item.id, MediaAsset.status == MediaStatus.ready)
    )).scalars().all()
    evaluations = (await session.execute(
        select(Evaluation).where(Evaluation.content_item_id == item.id).order_by(Evaluation.created_at.desc())
    )).scalars().all()
    latest_eval = evaluations[0] if evaluations else None
    media_score = max((a.quality_score or 0 for a in media), default=None)

    raw_payload = {
        "schema_version": "content-package/1.0",
        "content_id": str(item.id),
        "project_id": str(item.project_id),
        "status": "approved" if item.status == ContentStatus.ready else item.status.value,
        "canonical": {
            "content_type": item.type.value,
            "topic": item.topic,
            "goal": item.goal,
            "title": item.title,
            "body": item.body,
            "hook": item.hook,
            "cta": item.cta,
        },
        "variants": [{
            "platform": variant.platform,
            "title": variant.title,
            "plain_text": variant.body,
            "cta": variant.cta,
            "hashtags": variant.hashtags or [],
            "blocks": variant.blocks or [],
            "media": [{
                "asset_id": str(asset.id),
                "type": asset.type,
                "url": asset.url,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
            } for asset in media if asset.url],
        } for variant in variants],
        "sources": [{
            "id": source.get("id"),
            "title": source.get("title"),
            "url": source.get("url"),
            "score": source.get("score"),
        } for source in (item.research_sources or []) if source.get("url")],
        "quality": {
            "overall": item.quality_score,
            "factuality": latest_eval.factuality if latest_eval else None,
            "brand_voice": latest_eval.brand_voice if latest_eval else None,
            "media": media_score,
        },
    }
    payload = validate_content_package(raw_payload)
    delivery = ExportDelivery(content_item_id=item.id, payload=payload, status=ExportStatus.queued)
    session.add(delivery)
    await session.commit()
    return delivery


async def _deliver(session, delivery: ExportDelivery) -> None:
    if delivery.payload.get("status") != "approved":
        delivery.error = "Package is not approved; manual review is required before Autoposter delivery"
        delivery.status = ExportStatus.failed
        await session.commit()
        return

    delivery.status = ExportStatus.sending
    delivery.error = None
    await session.commit()
    try:
        result = await send_to_autoposter(
            delivery.payload,
            idempotency_key=f"{delivery.content_item_id}:{delivery.schema_version}",
        )
        if result.get("status") == "skipped":
            delivery.status = ExportStatus.queued
            delivery.error = result.get("reason")
        else:
            response = result.get("response") or {}
            delivery.external_id = response.get("id") or response.get("external_id")
            delivery.status = ExportStatus.accepted
            delivery.error = None
    except Exception as exc:
        delivery.status = ExportStatus.failed
        delivery.error = str(exc)[:4000]
    await session.commit()


async def _process(run_id: str) -> None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        run = await session.scalar(select(GenerationRun).where(GenerationRun.id == uuid.UUID(run_id)))
        if not run:
            return
        try:
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(timezone.utc)
            await session.commit()

            brand_profile = await session.scalar(select(BrandProfile).where(BrandProfile.project_id == run.project_id))
            brand = _brand_context(brand_profile)
            sources = await _research(session, run)

            step = await _stage(session, run, "draft", {
                "task": run.task,
                "content_type": run.content_type,
                "platforms": run.platforms,
                "sources_count": len(sources),
            })
            draft = await chat_json(
                "You are a senior content strategist and writer. Return JSON only. Never invent company or research facts.",
                f"""Create canonical content for the task. It must be useful before promotional.
Use research only when a claim is supported by the supplied sources. Do not fabricate citations.
Task: {run.task}
Content type: {run.content_type}
Target platforms: {run.platforms}
Brand: {json.dumps(brand, ensure_ascii=False)}
Research: {json.dumps(sources, ensure_ascii=False)}
Return {{"title":"","hook":"","body":"","cta":"","hashtags":[],"visual_prompt":"","topic":"","goal":"","source_refs":[]}}.""",
            )
            content_type = ContentType(run.content_type) if run.content_type in {x.value for x in ContentType} else ContentType.other
            item = ContentItem(
                project_id=run.project_id,
                type=content_type,
                status=ContentStatus.drafting,
                title=draft.get("title") or run.task[:200],
                task=run.task,
                topic=draft.get("topic"),
                goal=draft.get("goal"),
                platforms=run.platforms,
                research_sources=sources,
            )
            session.add(item)
            await session.flush()
            run.content_item_id = item.id
            await _save_version(session, item, run, "draft", draft)
            await _complete_step(session, step, draft)

            score = await _evaluate(session, run, item, brand, sources)
            attempt = 0
            while not _passes(score) and attempt < MAX_REVISIONS:
                attempt += 1
                step = await _stage(session, run, "revise", {"attempt": attempt, "notes": score.get("notes") or []})
                revised = await chat_json(
                    "You are a senior editor. Return JSON only. Preserve true claims and source_refs.",
                    f"""Improve the content using review notes. Do not add unsupported facts.
Brand: {json.dumps(brand, ensure_ascii=False)}
Research: {json.dumps(sources, ensure_ascii=False)}
Review: {json.dumps(score, ensure_ascii=False)}
Content: {json.dumps(item.structured_json, ensure_ascii=False)}
Return the same canonical JSON schema.""",
                )
                await _save_version(session, item, run, "revise", revised)
                await _complete_step(session, step, revised)
                score = await _evaluate(session, run, item, brand, sources)

            if not _passes(score):
                item.status = ContentStatus.review
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "quality_review"
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return

            step = await _stage(session, run, "humanize")
            humanized = await chat_json(
                "You are a natural-language editor. Remove generic AI cadence, clichés and sterile transitions without changing facts. Return JSON only.",
                f"""Brand: {json.dumps(brand, ensure_ascii=False)}
Rewrite naturally while preserving source_refs and factual meaning:
{json.dumps(item.structured_json, ensure_ascii=False)}
Return the same canonical JSON schema.""",
            )
            await _save_version(session, item, run, "humanize", humanized)
            await _complete_step(session, step, humanized)

            item.status = ContentStatus.adapting
            await session.commit()
            for platform in (run.platforms or ["telegram"]):
                step = await _stage(session, run, f"adapt:{platform}")
                variant = await chat_json(
                    "You are a platform editor. Preserve meaning and facts; adapt presentation only. Return JSON only.",
                    f"""Platform: {platform}
Canonical: {json.dumps(item.structured_json, ensure_ascii=False)}
Return {{"title":"","body":"","cta":"","hashtags":[],"blocks":[]}}.""",
                )
                session.add(ContentVariant(
                    content_item_id=item.id,
                    platform=platform,
                    title=variant.get("title"),
                    body=variant.get("body") or item.body or "",
                    cta=variant.get("cta"),
                    hashtags=variant.get("hashtags") or [],
                    blocks=variant.get("blocks") or [],
                ))
                await _complete_step(session, step, variant)

            media_asset: MediaAsset | None = None
            if (run.options or {}).get("generate_media", True):
                item.status = ContentStatus.generating_media
                await session.commit()
                media_asset = await _generate_media(session, run, item)

            final_score = await _evaluate(session, run, item, brand, sources, stage_name="final_evaluate")
            media_required = bool((run.options or {}).get("generate_media", True))
            media_ok = not media_required or (media_asset is not None and media_asset.status == MediaStatus.ready)
            if _passes(final_score) and media_ok:
                item.status = ContentStatus.ready
                run.status = GenerationRunStatus.ready
                run.current_stage = "ready"
            else:
                item.status = ContentStatus.final_review
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "final_review"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

            step = await _stage(session, run, "package", provider="internal", model=None)
            delivery = await _package(session, item)
            await _complete_step(session, step, {"delivery_id": str(delivery.id), "status": delivery.status.value})

            if (run.options or {}).get("auto_export", False) and item.status == ContentStatus.ready:
                await _deliver(session, delivery)
        except Exception as exc:
            await session.rollback()
            run = await session.scalar(select(GenerationRun).where(GenerationRun.id == uuid.UUID(run_id)))
            if run:
                running_step = await session.scalar(
                    select(GenerationStep)
                    .where(GenerationStep.run_id == run.id, GenerationStep.status == GenerationStepStatus.running)
                    .order_by(GenerationStep.created_at.desc())
                )
                if running_step:
                    running_step.status = GenerationStepStatus.failed
                    running_step.error = str(exc)[:4000]
                run.status = GenerationRunStatus.failed
                run.error = str(exc)[:4000]
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
            raise


async def _send_delivery(delivery_id: str) -> None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        delivery = await session.scalar(select(ExportDelivery).where(ExportDelivery.id == uuid.UUID(delivery_id)))
        if not delivery:
            return
        await _deliver(session, delivery)


@app.task(name="content_factory.process_run")
def process_run(run_id: str) -> None:
    asyncio.run(_process(run_id))


@app.task(name="content_factory.send_delivery")
def send_delivery(delivery_id: str) -> None:
    asyncio.run(_send_delivery(delivery_id))
