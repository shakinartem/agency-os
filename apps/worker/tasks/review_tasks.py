"""Human-review continuation tasks.

A human approval overrides canonical text scoring, but it does not bypass downstream
platform adaptation, media QA or package validation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import delete, select

from database.base import get_async_session_maker
from database.enums import ContentStatus, GenerationRunStatus, MediaStatus
from database.models import BrandProfile, ContentItem, ContentVariant, GenerationRun, MediaAsset

from .factory_worker import _brand_context, _complete_step, _generate_media, _package, _stage
from .providers import chat_json


async def _resume_human_approved(content_id: str) -> None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        item = await session.scalar(select(ContentItem).where(ContentItem.id == uuid.UUID(content_id)))
        if not item:
            return

        run = await session.scalar(
            select(GenerationRun)
            .where(GenerationRun.content_item_id == item.id)
            .order_by(GenerationRun.created_at.desc())
        )
        if run is None:
            run = GenerationRun(
                project_id=item.project_id,
                content_item_id=item.id,
                task=item.task or item.topic or item.title,
                content_type=item.type.value,
                platforms=item.platforms or ["telegram"],
                options={"use_research": False, "generate_media": bool(item.visual_prompt), "auto_export": False, "human_review_resume": True},
                status=GenerationRunStatus.running,
                current_stage="human_approved",
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.commit()

        try:
            brand_profile = await session.scalar(select(BrandProfile).where(BrandProfile.project_id == item.project_id))
            brand = _brand_context(brand_profile)

            # Existing platform copies are derived from an older canonical version and must not
            # silently survive a manual review/edit.
            await session.execute(delete(ContentVariant).where(ContentVariant.content_item_id == item.id))
            await session.commit()

            item.status = ContentStatus.adapting
            await session.commit()
            for platform in (item.platforms or run.platforms or ["telegram"]):
                step = await _stage(session, run, f"adapt:{platform}:human_approved")
                variant = await chat_json(
                    "You are a platform editor. The canonical text was approved by a human. Preserve its facts and intent exactly; adapt presentation only. Return JSON only.",
                    f"""Platform: {platform}
Brand: {json.dumps(brand, ensure_ascii=False)}
Canonical: {json.dumps(item.structured_json or {"title": item.title, "body": item.body, "hook": item.hook, "cta": item.cta}, ensure_ascii=False)}
Return {{"title":"","body":"","cta":"","hashtags":[],"blocks":[]}}.""",
                )
                session.add(ContentVariant(
                    content_item_id=item.id,
                    platform=platform,
                    title=variant.get("title"),
                    body=variant.get("body") or item.body or "",
                    cta=variant.get("cta") or item.cta,
                    hashtags=variant.get("hashtags") or [],
                    blocks=variant.get("blocks") or [],
                ))
                await _complete_step(session, step, variant)

            media_required = bool((run.options or {}).get("generate_media", True))
            media_asset = None
            if media_required:
                # Old accepted images may describe an earlier version of the text. Keep their
                # records for audit, but remove them from the set eligible for the next package.
                old_media = (await session.execute(
                    select(MediaAsset).where(MediaAsset.content_item_id == item.id, MediaAsset.status == MediaStatus.ready)
                )).scalars().all()
                for asset in old_media:
                    asset.status = MediaStatus.review
                    metadata = dict(asset.metadata_json or {})
                    metadata["superseded_by_human_review"] = True
                    asset.metadata_json = metadata
                await session.commit()

                item.status = ContentStatus.generating_media
                await session.commit()
                media_asset = await _generate_media(session, run, item)

            media_ok = not media_required or (media_asset is not None and media_asset.status == MediaStatus.ready)
            if media_ok:
                item.status = ContentStatus.ready
                run.status = GenerationRunStatus.ready
                run.current_stage = "human_approved_ready"
            else:
                item.status = ContentStatus.final_review
                run.status = GenerationRunStatus.awaiting_review
                run.current_stage = "media_review"
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

            step = await _stage(session, run, "package:human_approved", provider="internal", model=None)
            delivery = await _package(session, item)
            await _complete_step(session, step, {"delivery_id": str(delivery.id), "status": delivery.status.value})
        except Exception as exc:
            await session.rollback()
            item = await session.scalar(select(ContentItem).where(ContentItem.id == uuid.UUID(content_id)))
            run = await session.scalar(
                select(GenerationRun)
                .where(GenerationRun.content_item_id == uuid.UUID(content_id))
                .order_by(GenerationRun.created_at.desc())
            )
            if item:
                item.status = ContentStatus.failed
            if run:
                run.status = GenerationRunStatus.failed
                run.error = str(exc)[:4000]
                run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            raise


@shared_task(name="content_factory.approve_content")
def approve_content(content_id: str) -> None:
    asyncio.run(_resume_human_approved(content_id))
