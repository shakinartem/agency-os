"""Content Factory background worker.

The pipeline is deliberately deterministic: each stage is persisted and may be retried
independently later. Provider calls are isolated behind small adapters.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from celery import Celery
from sqlalchemy import select

from database.base import get_async_session_maker
from database.enums import ContentStatus, ContentType, ExportStatus, GenerationRunStatus, GenerationStepStatus, MediaStatus
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

broker_url = os.getenv("REDIS_URL", "redis://localhost:6380/0")
app = Celery("content_factory_worker", broker=broker_url)
app.conf.broker_connection_retry_on_startup = True

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.6")
IMAGE_API_URL = os.getenv("IMAGE_API_URL")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY") or LLM_API_KEY
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1.5")
AUTOPOSTER_URL = os.getenv("AUTOPOSTER_URL")
AUTOPOSTER_TOKEN = os.getenv("AUTOPOSTER_TOKEN")
QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", "0.87"))
FACTUALITY_THRESHOLD = float(os.getenv("FACTUALITY_THRESHOLD", "0.95"))
BRAND_VOICE_THRESHOLD = float(os.getenv("BRAND_VOICE_THRESHOLD", "0.85"))
MAX_REVISIONS = int(os.getenv("MAX_REVISION_ATTEMPTS", "2"))
PROMPT_VERSION = "factory-v1"


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {"body": text}


async def _llm(system: str, prompt: str) -> dict[str, Any]:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return _parse_json(data["choices"][0]["message"]["content"])


def _brand_context(profile: BrandProfile | None) -> str:
    if not profile:
        return "Brand profile is not configured. Do not invent company facts."
    return json.dumps({
        "positioning": profile.positioning,
        "audience": profile.audience,
        "products": profile.products,
        "tone_of_voice": profile.tone_of_voice,
        "brand_rules": profile.brand_rules,
        "forbidden_claims": profile.forbidden_claims,
        "examples": profile.examples,
    }, ensure_ascii=False)


async def _stage(session, run: GenerationRun, name: str, payload: dict[str, Any] | None = None) -> GenerationStep:
    run.current_stage = name
    step = GenerationStep(
        run_id=run.id,
        stage=name,
        status=GenerationStepStatus.running,
        provider="openai-compatible" if name not in {"package", "export"} else "internal",
        model=LLM_MODEL if name not in {"package", "export"} else None,
        prompt_version=PROMPT_VERSION,
        input_json=payload or {},
    )
    session.add(step)
    await session.flush()
    return step


async def _complete_step(session, step: GenerationStep, output: dict[str, Any], status: GenerationStepStatus = GenerationStepStatus.passed):
    step.output_json = output
    step.status = status
    await session.flush()


async def _save_version(session, item: ContentItem, run: GenerationRun, stage: str, data: dict[str, Any]):
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


async def _evaluate(session, run: GenerationRun, item: ContentItem, brand: str) -> dict[str, Any]:
    step = await _stage(session, run, "evaluate", {"content_item_id": str(item.id)})
    result = await _llm(
        "You are a strict senior content editor and fact-risk reviewer. Return JSON only.",
        f"""Evaluate this content from 0 to 1. Do not reward polished nonsense. Factuality means claims are either supported by supplied brand context or clearly framed without invented facts.
Brand context: {brand}
Content: {json.dumps(item.structured_json or {"title": item.title, "body": item.body}, ensure_ascii=False)}
Return exactly: {{"overall":0.0,"factuality":0.0,"brand_voice":0.0,"clarity":0.0,"hook":0.0,"usefulness":0.0,"originality":0.0,"policy_passed":true,"notes":[]}}""",
    )
    ev = Evaluation(
        content_item_id=item.id,
        run_id=run.id,
        stage="evaluate",
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


def _passes(score: dict[str, Any]) -> bool:
    return (
        float(score.get("overall", 0)) >= QUALITY_THRESHOLD
        and float(score.get("factuality", 0)) >= FACTUALITY_THRESHOLD
        and float(score.get("brand_voice", 0)) >= BRAND_VOICE_THRESHOLD
        and bool(score.get("policy_passed", False))
    )


async def _generate_image(session, run: GenerationRun, item: ContentItem) -> MediaAsset | None:
    prompt = item.visual_prompt
    if not prompt:
        return None
    asset = MediaAsset(content_item_id=item.id, run_id=run.id, prompt=prompt, status=MediaStatus.generating, provider="openai-compatible", model=IMAGE_MODEL)
    session.add(asset)
    await session.flush()
    if not IMAGE_API_URL or not IMAGE_API_KEY:
        asset.status = MediaStatus.review
        asset.metadata_json = {"reason": "IMAGE_API_URL or IMAGE_API_KEY is not configured"}
        return asset
    headers = {"Authorization": f"Bearer {IMAGE_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(IMAGE_API_URL, headers=headers, json={"model": IMAGE_MODEL, "prompt": prompt, "size": "1024x1024"})
        response.raise_for_status()
        data = response.json()
    first = (data.get("data") or [{}])[0]
    asset.url = first.get("url")
    asset.metadata_json = {"b64_json": first.get("b64_json")} if first.get("b64_json") else {}
    asset.status = MediaStatus.ready if (asset.url or first.get("b64_json")) else MediaStatus.review
    asset.quality_score = 1.0 if asset.status == MediaStatus.ready else None
    return asset


async def _build_export(session, item: ContentItem, auto_export: bool) -> ExportDelivery:
    variants = (await session.execute(select(ContentVariant).where(ContentVariant.content_item_id == item.id))).scalars().all()
    media = (await session.execute(select(MediaAsset).where(MediaAsset.content_item_id == item.id, MediaAsset.status == MediaStatus.ready))).scalars().all()
    payload = {
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
        },
        "variants": [{
            "platform": v.platform,
            "title": v.title,
            "plain_text": v.body,
            "cta": v.cta,
            "hashtags": v.hashtags or [],
            "blocks": v.blocks or [],
            "media": [{"asset_id": str(a.id), "type": a.type, "url": a.url, "mime_type": a.mime_type} for a in media],
        } for v in variants],
        "quality": {"overall": item.quality_score},
    }
    delivery = ExportDelivery(content_item_id=item.id, payload=payload, status=ExportStatus.queued)
    session.add(delivery)
    await session.flush()

    if auto_export and AUTOPOSTER_URL:
        delivery.status = ExportStatus.sending
        headers = {"Content-Type": "application/json"}
        if AUTOPOSTER_TOKEN:
            headers["Authorization"] = f"Bearer {AUTOPOSTER_TOKEN}"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(AUTOPOSTER_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json() if response.content else {}
        delivery.external_id = result.get("id") or result.get("external_id")
        delivery.status = ExportStatus.accepted
    return delivery


async def _process(run_id: str):
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        run = await session.scalar(select(GenerationRun).where(GenerationRun.id == uuid.UUID(run_id)))
        if not run:
            return
        try:
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(timezone.utc)
            brand_profile = await session.scalar(select(BrandProfile).where(BrandProfile.project_id == run.project_id))
            brand = _brand_context(brand_profile)

            step = await _stage(session, run, "draft", {"task": run.task, "content_type": run.content_type, "platforms": run.platforms})
            draft = await _llm(
                "You are a senior content strategist and writer. Return JSON only. Never invent company facts.",
                f"""Create canonical content for the task below. It must be useful before it is promotional.
Task: {run.task}
Content type: {run.content_type}
Target platforms: {run.platforms}
Brand: {brand}
Return {{"title":"","hook":"","body":"","cta":"","hashtags":[],"visual_prompt":"","topic":"","goal":""}}.""",
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
            )
            session.add(item)
            await session.flush()
            run.content_item_id = item.id
            await _save_version(session, item, run, "draft", draft)
            await _complete_step(session, step, draft)

            score = await _evaluate(session, run, item, brand)
            attempt = 0
            while not _passes(score) and attempt < MAX_REVISIONS:
                attempt += 1
                step = await _stage(session, run, "revise", {"attempt": attempt, "notes": score.get("notes", [])})
                revised = await _llm(
                    "You are a senior editor. Return JSON only and preserve true claims.",
                    f"Improve this content using the review notes. Brand: {brand}\nReview: {json.dumps(score, ensure_ascii=False)}\nContent: {json.dumps(item.structured_json, ensure_ascii=False)}\nReturn the same content JSON schema.",
                )
                await _save_version(session, item, run, "revise", revised)
                await _complete_step(session, step, revised)
                score = await _evaluate(session, run, item, brand)

            if not _passes(score):
                item.status = ContentStatus.review
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "quality_review"
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return

            step = await _stage(session, run, "humanize")
            humanized = await _llm(
                "You are a natural-language editor. Remove generic AI cadence, clichés and sterile transitions without changing facts. Return JSON only.",
                f"Brand: {brand}\nRewrite naturally: {json.dumps(item.structured_json, ensure_ascii=False)}\nReturn the same content JSON schema.",
            )
            await _save_version(session, item, run, "humanize", humanized)
            await _complete_step(session, step, humanized)

            item.status = ContentStatus.adapting
            for platform in (run.platforms or ["telegram"]):
                step = await _stage(session, run, f"adapt:{platform}")
                variant = await _llm(
                    "You are a platform editor. Preserve meaning, adapt presentation. Return JSON only.",
                    f"Platform: {platform}\nCanonical: {json.dumps(item.structured_json, ensure_ascii=False)}\nReturn {{" + '"title":"","body":"","cta":"","hashtags":[],"blocks":[]' + "}}.",
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

            media_asset = None
            if (run.options or {}).get("generate_media", True):
                run.current_stage = "generating_media"
                media_asset = await _generate_image(session, run, item)

            final_score = await _evaluate(session, run, item, brand)
            media_ok = media_asset is None or media_asset.status == MediaStatus.ready
            if _passes(final_score) and media_ok:
                item.status = ContentStatus.ready
                run.status = GenerationRunStatus.ready
                run.current_stage = "ready"
            else:
                item.status = ContentStatus.final_review
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "final_review"

            await _build_export(session, item, auto_export=bool((run.options or {}).get("auto_export", False) and run.status == GenerationRunStatus.ready))
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as exc:
            run.status = GenerationRunStatus.failed
            run.error = str(exc)[:4000]
            run.current_stage = "failed"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            raise


@app.task(name="content_factory.process_run")
def process_run(run_id: str):
    return asyncio.run(_process(run_id))
