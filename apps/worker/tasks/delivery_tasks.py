"""Autoposter delivery with delivery-scoped idempotency."""

from __future__ import annotations

import asyncio
import uuid

from celery import shared_task
from sqlalchemy import select

from database.base import get_async_session_maker
from database.enums import ExportStatus
from database.models import ExportDelivery

from .providers import send_to_autoposter


async def _send_delivery_v2(delivery_id: str) -> None:
    maker = get_async_session_maker()
    async with maker() as session:
        delivery = await session.scalar(select(ExportDelivery).where(ExportDelivery.id == uuid.UUID(delivery_id)))
        if delivery is None:
            return
        if delivery.status == ExportStatus.accepted:
            return
        if delivery.payload.get("status") != "approved":
            delivery.status = ExportStatus.failed
            delivery.error = "Package is not approved"
            await session.commit()
            return

        delivery.status = ExportStatus.sending
        delivery.error = None
        await session.commit()
        try:
            result = await send_to_autoposter(
                delivery.payload,
                idempotency_key=f"content-factory-delivery:{delivery.id}",
            )
            if result.get("status") == "skipped":
                delivery.status = ExportStatus.queued
                delivery.error = result.get("reason")
            else:
                response = result.get("response") or {}
                delivery.external_id = response.get("receipt_id") or response.get("id") or response.get("external_id")
                delivery.status = ExportStatus.accepted
                delivery.error = None
        except Exception as exc:
            delivery.status = ExportStatus.failed
            delivery.error = str(exc)[:4000]
        await session.commit()


@shared_task(name="content_factory.send_delivery_v2")
def send_delivery_v2(delivery_id: str) -> None:
    asyncio.run(_send_delivery_v2(delivery_id))
