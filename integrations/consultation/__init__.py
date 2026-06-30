"""Consultation integration adapter — mock for bot2_consultation_ai.

Manages AI-driven consultation sessions, generates summaries
and detects intent from conversations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrations.base import BaseIntegration


class ConsultationIntegration(BaseIntegration):
    """Adapter for bot2_consultation_ai — AI consultation engine."""

    service_name: str = "bot2_consultation_ai"

    async def pull(self) -> list[dict[str, Any]]:
        """Mock: return pending consultation sessions."""
        return [
            {
                "session_id": "cs_001",
                "lead_name": "Ivan Petrov",
                "question": "Looking for a marketing strategy",
                "intent": "lead_generation",
                "status": "pending",
                "created_at": "2026-06-29T08:00:00Z",
            },
            {
                "session_id": "cs_002",
                "lead_name": "Olga Smirnova",
                "question": "How to automate Instagram posting?",
                "intent": "automation",
                "status": "completed",
                "summary": "Client needs an autoposter for Instagram feed and stories.",
                "created_at": "2026-06-28T16:00:00Z",
            },
        ]

    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mock: send a consultation request to the AI service."""
        return {
            "success": True,
            "session_id": f"cs_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "response": {
                "summary": "Consultation request received and queued for AI processing.",
                "estimated_completion_minutes": 2,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert consultation record -> Agency OS conversation / intent DTO."""
        return {
            "external_session_id": raw_data.get("session_id"),
            "lead_name": raw_data.get("lead_name"),
            "question": raw_data.get("question"),
            "intent": raw_data.get("intent"),
            "ai_summary": raw_data.get("summary"),
            "status": raw_data.get("status", "pending"),
        }
