"""FastAPI-side helpers for the shared transactional task outbox."""

from __future__ import annotations

from celery import Celery

from database.task_outbox import enqueue_task

__all__ = ["enqueue_task", "nudge_dispatcher"]


def nudge_dispatcher(queue: Celery) -> None:
    """Best-effort low-latency nudge; Celery Beat is the durable retry path."""
    try:
        queue.send_task("content_factory.dispatch_task_outbox")
    except Exception:
        pass
