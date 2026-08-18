"""Background materialization of expensive Model Router evidence scans."""
from __future__ import annotations

import asyncio
import os
import uuid

from celery import shared_task

from database.base import get_async_session_maker
from database.model_router_cache import store_model_router_refresh_error, store_model_router_snapshot
from database.model_router_outcomes import build_model_router_report


async def _refresh(project_id: str) -> dict[str, str]:
    project_uuid = uuid.UUID(project_id)
    default_model = os.getenv("LLM_MODEL", "gpt-5.6")
    maker = get_async_session_maker()
    async with maker() as session:
        try:
            report = await build_model_router_report(session, project_uuid, default_model=default_model)
            await store_model_router_snapshot(session, project_uuid, default_model, report)
            await session.commit()
            return {"status": "ready", "project_id": project_id}
        except Exception as exc:
            await session.rollback()
            await store_model_router_refresh_error(session, project_uuid, default_model, str(exc))
            await session.commit()
            raise


@shared_task(name="content_factory.refresh_model_router_snapshot")
def refresh_model_router_snapshot(project_id: str) -> dict[str, str]:
    return asyncio.run(_refresh(project_id))
