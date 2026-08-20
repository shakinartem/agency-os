"""PostgreSQL contract for transactional task deduplication."""

import asyncio
import uuid

from sqlalchemy import delete

from database.base import get_async_session_maker
from database.models import TaskOutbox
from database.task_outbox import enqueue_task


async def _scenario():
    maker = get_async_session_maker()
    key = f"test:{uuid.uuid4()}"
    async with maker() as session:
        first = await enqueue_task(session, "content_factory.test", args=["one"], dedupe_key=key)
        await session.commit()
        first_id = first.id
        second = await enqueue_task(session, "content_factory.test", args=["different-ignored"], dedupe_key=key)
        await session.commit()
        assert second.id == first_id
        await session.execute(delete(TaskOutbox).where(TaskOutbox.id == first_id))
        await session.commit()


def test_transactional_task_outbox_deduplicates_commands():
    asyncio.run(_scenario())
