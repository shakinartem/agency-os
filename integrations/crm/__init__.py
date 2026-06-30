"""CRM integration adapter — mock for bot1_crm.

Connects to an external CRM (e.g. Bitrix24, AmoCRM) and syncs
contacts / deals as Agency OS leads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrations.base import BaseIntegration


class CRMIntegration(BaseIntegration):
    """Adapter for bot1_crm — lead / contact management."""

    service_name: str = "bot1_crm"

    async def pull(self) -> list[dict[str, Any]]:
        """Mock: return a list of leads from the CRM."""
        return [
            {
                "id": "crm_001",
                "name": "Ivan Petrov",
                "phone": "+7-900-111-22-33",
                "email": "ivan@example.com",
                "source": "telegram",
                "status": "new",
                "created_at": "2026-06-28T10:00:00Z",
            },
            {
                "id": "crm_002",
                "name": "Anna Sidorova",
                "phone": "+7-900-444-55-66",
                "email": "anna@example.com",
                "source": "website",
                "status": "contacted",
                "created_at": "2026-06-27T14:30:00Z",
            },
        ]

    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mock: create / update a lead in the CRM."""
        return {
            "success": True,
            "external_id": f"crm_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "record": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert CRM record -> Agency OS lead DTO."""
        return {
            "external_id": raw_data.get("id"),
            "name": raw_data.get("name", ""),
            "phone": raw_data.get("phone"),
            "telegram": raw_data.get("telegram"),
            "whatsapp": raw_data.get("whatsapp"),
            "email": raw_data.get("email"),
            "status": raw_data.get("status", "new"),
            "source": self._map_source(raw_data.get("source", "manual")),
        }

    @staticmethod
    def _map_source(source: str) -> str:
        mapping = {
            "telegram": "telegram",
            "whatsapp": "whatsapp",
            "site": "website",
            "referral": "referral",
        }
        return mapping.get(source, "manual")
