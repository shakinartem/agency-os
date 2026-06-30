"""Reports integration adapter — mock for bot5_otchet.

Generates performance reports and analytics snapshots
aggregated from CRM, consultations, content and publications.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from integrations.base import BaseIntegration


class ReportsIntegration(BaseIntegration):
    """Adapter for bot5_otchet — reporting & analytics."""

    service_name: str = "bot5_otchet"

    async def pull(self) -> list[dict[str, Any]]:
        """Mock: return pre-generated report snapshots from the external service."""
        return [
            {
                "report_id": "rpt_001",
                "period_start": "2026-06-01",
                "period_end": "2026-06-28",
                "metrics": {
                    "total_leads": 47,
                    "converted_leads": 12,
                    "consultations": 23,
                    "content_generated": 15,
                    "publications": 31,
                    "avg_response_time_hours": 1.5,
                    "top_source": "telegram",
                },
                "generated_at": "2026-06-28T23:59:00Z",
            },
            {
                "report_id": "rpt_002",
                "period_start": "2026-05-01",
                "period_end": "2026-05-31",
                "metrics": {
                    "total_leads": 38,
                    "converted_leads": 9,
                    "consultations": 18,
                    "content_generated": 12,
                    "publications": 25,
                    "avg_response_time_hours": 2.1,
                    "top_source": "website",
                },
                "generated_at": "2026-05-31T23:59:00Z",
            },
        ]

    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mock: request a new report generation."""
        return {
            "success": True,
            "report_id": f"rpt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "period_start": data.get("period_start"),
            "period_end": data.get("period_end"),
            "status": "generating",
            "estimated_completion_seconds": 30,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert external report -> Agency OS ReportSnapshot DTO."""
        return {
            "external_id": raw_data.get("report_id"),
            "period_start": raw_data.get("period_start", ""),
            "period_end": raw_data.get("period_end", ""),
            "metrics": raw_data.get("metrics", {}),
            "generated_at": raw_data.get("generated_at"),
        }
