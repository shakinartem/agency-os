"""Base integration adapter — defines the interface all adapters must implement.

Provides shared logic for healthcheck, error logging, and HTTP transport.
Subclasses override sync/pull/push/normalize with service-specific logic.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BaseIntegration(ABC):
    """Abstract adapter that each external-service integration must implement.

    Parameters
    ----------
    config_id : str | uuid.UUID
        The IntegrationConfig.id this adapter belongs to.
    base_url : str | None
        The service endpoint root.
    api_key : str | None
        Authentication token / API key for the external service.
    """

    # Human-readable service name — override in subclass
    service_name: str = "unknown"

    def __init__(
        self,
        config_id: str | uuid.UUID,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.config_id = str(config_id)
        self.base_url = base_url
        self.api_key = api_key
        self._http_client: httpx.AsyncClient | None = None

    # ── HTTP helpers ─────────────────────────────────────

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers.setdefault("Authorization", f"Bearer {self.api_key}")
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(15.0),
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Healthcheck ──────────────────────────────────────

    async def healthcheck(self) -> dict[str, Any]:
        """Ping the remote service and return status + latency (ms)."""
        start = time.monotonic()
        status = "healthy"
        error: str | None = None
        try:
            client = await self._get_http_client()
            resp = await client.get("/health")
            resp.raise_for_status()
        except Exception as exc:
            status = "down"
            error = str(exc)
        finally:
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "service": self.service_name,
            "config_id": self.config_id,
            "status": status,
            "latency_ms": elapsed_ms,
            "error": error,
        }

    # ── Sync ─────────────────────────────────────────────

    async def sync(self) -> dict[str, Any]:
        """Pull new data from the remote service and return a sync summary."""
        pulled = await self.pull()
        count = len(pulled) if isinstance(pulled, list) else 0
        return {
            "service": self.service_name,
            "config_id": self.config_id,
            "action": "sync",
            "items_pulled": count,
            "items_pushed": 0,
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Pull ─────────────────────────────────────────────

    @abstractmethod
    async def pull(self) -> list[dict[str, Any]]:
        """Retrieve raw records from the external service and return them as a list of dicts."""
        ...

    # ── Push ─────────────────────────────────────────────

    @abstractmethod
    async def push(self, data: dict[str, Any]) -> dict[str, Any]:
        """Send data to the external service. Return the service's response."""
        ...

    # ── Normalize ────────────────────────────────────────

    @abstractmethod
    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw record from the service's format into Agency OS DTO shape."""
        ...

    # ── Error logging ────────────────────────────────────

    async def log_error(self, error: Exception | str) -> dict[str, Any]:
        """Build a structured error payload that can be written to IntegrationLog."""
        message = str(error)
        logger.warning("[%s] %s", self.service_name, message)
        return {
            "integration_config_id": self.config_id,
            "action": "other",
            "status": "failed",
            "payload": {"error_type": type(error).__name__},
            "error": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
