"""Autoposter integration adapter — mock for autoposter_bot.

Schedules and publishes content to external platforms
(Telegram, Instagram, Facebook, VK, website).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrations.base import BaseIntegration


class AutoposterIntegration(BaseIntegration):
    """Adapter for autoposter_bot — cross-platform content publishing."""

    service_name: str = "autoposter_bot"

    async def pull(self) -> list[dict[str, Any]]:
        """Mock: return publication statuses from external platforms."""
        return [
            {
                "pub_id": "ap_001",
                "platform": "telegram",
                "content_title": "10 Ways to Boost Engagement",
                "status": "published",
                "published_at": "2026-06-29T07:00:00Z",
                "url": "https://t.me/agency_os/123",
                "stats": {"views": 450, "clicks": 32},
            },
            {
                "pub_id": "ap_002",
                "platform": "instagram",
                "content_title": "Behind the Scenes",
                "status": "scheduled",
                "scheduled_at": "2026-06-30T10:00:00Z",
                "url": None,
                "stats": None,
            },
        ]

    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mock: publish or schedule content on a target platform."""
        platform = data.get("platform", "unknown")
        return {
            "success": True,
            "pub_id": f"ap_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "platform": platform,
            "status": "scheduled" if data.get("scheduled_at") else "published",
            "url": f"https://{platform}.example.com/post/{datetime.now(timezone.utc).timestamp():.0f}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert autoposter record -> Agency OS Publication DTO."""
        return {
            "external_id": raw_data.get("pub_id"),
            "platform": raw_data.get("platform", "other"),
            "status": raw_data.get("status", "scheduled"),
            "scheduled_at": raw_data.get("scheduled_at"),
            "published_at": raw_data.get("published_at"),
            "url": raw_data.get("url"),
            "stats": raw_data.get("stats"),
        }
