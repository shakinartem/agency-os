"""Celery delivery for the transactional PostgreSQL task outbox.

PostgreSQL owns enqueue intent. The dispatcher publishes a single generic executor
message carrying the durable outbox id. The executor claims the row before invoking the
registered domain task, which suppresses duplicate broker deliveries. A process crash
mid-execution is deliberately surfaced as `stale_execution` instead of being blindly
replayed, because generation tasks can have expensive/non-idempotent side effects.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select, update

from database.base import get_async_session_maker
from database.models import TaskOutbox

from .factory_worker import app

app.conf.beat_schedule = {
    "dispatch-transactional-task-outbox": {
        "task": "content_factory.dispatch_task_outbox",
        "schedule": float(os.getenv("TASK_OUTBOX_DISPATCH_INTERVAL_SECONDS", "2")),
    }
}

DISPATCH_BATCH = int(os.getenv("TASK_OUTBOX_DISPATCH_BATCH", "50"))
STALE_DISPATCH_SECONDS = int(os.getenv("TASK_OUTBOX_STALE_SECONDS", "300"))
STALE_EXECUTION_SECONDS = int(os.getenv("TASK_OUTBOX_STALE_EXECUTION_SECONDS", "1800"))


async def _dispatch_pending() -> int:
    session_maker = get_async_session_maker()
    sent = 0
    async with session_maker() as session:
        now = datetime.now(timezone.utc)
        await session.execute(
            update(TaskOutbox)
            .where(TaskOutbox.status == "dispatching", TaskOutbox.updated_at < now - timedelta(seconds=STALE_DISPATCH_SECONDS))
            .values(status="pending", last_error="Recovered stale broker-dispatch claim")
        )
        await session.execute(
            update(TaskOutbox)
            .where(TaskOutbox.status == "executing", TaskOutbox.updated_at < now - timedelta(seconds=STALE_EXECUTION_SECONDS))
            .values(status="stale_execution", last_error="Worker disappeared during domain execution; inspect before retry")
        )
        await session.commit()

        rows = (
            await session.execute(
                select(TaskOutbox)
                .where(TaskOutbox.status.in_(["pending", "failed"]), TaskOutbox.available_at <= now)
                .order_by(TaskOutbox.created_at.asc())
                .limit(DISPATCH_BATCH)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        for row in rows:
            row.status = "dispatching"
            row.attempts += 1
            row.last_error = None
            await session.commit()
            try:
                app.send_task(
                    "content_factory.execute_outbox_task",
                    args=[str(row.id)],
                    task_id=f"content-factory-outbox-{row.id}",
                )
                row.status = "sent"
                row.sent_at = datetime.now(timezone.utc)
                sent += 1
            except Exception as exc:
                row.status = "failed"
                row.last_error = str(exc)[:4000]
                delay = min(300, max(2, 2 ** min(row.attempts, 8)))
                row.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            await session.commit()
    return sent


async def _claim_execution(outbox_id: str) -> tuple[str, list, dict] | None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        row = await session.scalar(select(TaskOutbox).where(TaskOutbox.id == uuid.UUID(outbox_id)).with_for_update())
        if row is None or row.status in {"executing", "completed", "stale_execution"}:
            return None
        if row.status not in {"sent", "dispatching"}:
            return None
        row.status = "executing"
        row.last_error = None
        await session.commit()
        return row.task_name, list(row.args_json or []), dict(row.kwargs_json or {})


async def _finish_execution(outbox_id: str, *, success: bool, error: str | None = None) -> None:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        row = await session.scalar(select(TaskOutbox).where(TaskOutbox.id == uuid.UUID(outbox_id)))
        if row is None:
            return
        if success:
            row.status = "completed"
            row.last_error = None
        else:
            row.status = "failed"
            row.last_error = (error or "Task failed")[:4000]
            delay = min(300, max(2, 2 ** min(row.attempts, 8)))
            row.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await session.commit()


@shared_task(name="content_factory.dispatch_task_outbox")
def dispatch_task_outbox() -> int:
    return asyncio.run(_dispatch_pending())


@shared_task(name="content_factory.execute_outbox_task")
def execute_outbox_task(outbox_id: str):
    claimed = asyncio.run(_claim_execution(outbox_id))
    if claimed is None:
        return {"status": "duplicate_or_not_runnable"}
    task_name, args, kwargs = claimed
    try:
        target = app.tasks.get(task_name)
        if target is None:
            raise RuntimeError(f"Task is not registered: {task_name}")
        result = target.run(*args, **kwargs)
        asyncio.run(_finish_execution(outbox_id, success=True))
        return {"status": "completed", "task_name": task_name, "result": result}
    except Exception as exc:
        asyncio.run(_finish_execution(outbox_id, success=False, error=str(exc)))
        raise
