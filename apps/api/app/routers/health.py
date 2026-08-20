"""Liveness and readiness probes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import config
from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Process liveness only; does not touch dependencies."""
    return {"status": "ok", "service": "content-factory-api", "version": config.app_version}


@router.get("/ready")
async def readiness(response: Response, db: AsyncSession = Depends(get_db)):
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        redis = Redis.from_url(config.redis_url, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if healthy else "not_ready", **checks}


@router.get("/health/full")
async def health_full(response: Response, db: AsyncSession = Depends(get_db)):
    """Compatibility alias for readiness."""
    return await readiness(response, db)
