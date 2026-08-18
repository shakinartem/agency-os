"""Read-only cached Model Router diagnostics."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database.model_router_cache import get_cached_model_router_report
from database.models import User

from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/model-routing", tags=["model-routing"])


@router.get("/report")
async def model_routing_report(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    default_model = os.getenv("LLM_MODEL", "gpt-5.6")
    report = await get_cached_model_router_report(
        db,
        project_id,
        default_model=default_model,
        schedule_refresh=True,
    )
    return {"project_id": str(project_id), **report}
