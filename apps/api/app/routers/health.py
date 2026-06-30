"""Health endpoints — liveness and readiness probes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Simple liveness probe."""
    return {"status": "ok", "service": "agency-os-api"}


@router.get("/health/full")
async def health_full(db: AsyncSession = Depends(get_db)):
    """Readiness probe — checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "api": "ok",
        "database": db_status,
    }