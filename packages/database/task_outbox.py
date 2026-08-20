"""Shared transactional task outbox helpers.

The caller persists domain state and the enqueue intent in the same PostgreSQL
transaction. Redis/Celery becomes a delivery mechanism rather than the source of truth.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TaskOutbox


async def enqueue_task(
    db: AsyncSession,
    task_name: str,
    *,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> TaskOutbox:
    values = {
        "task_name": task_name,
        "args_json": args or [],
        "kwargs_json": kwargs or {},
        "status": "pending",
        "dedupe_key": dedupe_key,
    }
    if dedupe_key:
        result = await db.execute(
            insert(TaskOutbox)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[TaskOutbox.dedupe_key])
            .returning(TaskOutbox.id)
        )
        row_id = result.scalar_one_or_none()
        if row_id is None:
            existing = await db.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == dedupe_key))
            if existing is None:
                raise RuntimeError("Task outbox dedupe conflict could not be resolved")
            return existing
        row = await db.get(TaskOutbox, row_id)
        if row is None:
            raise RuntimeError("Task outbox row disappeared after insert")
        return row

    row = TaskOutbox(**values)
    db.add(row)
    await db.flush()
    return row
