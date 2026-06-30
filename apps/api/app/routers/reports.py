"""/reports/snapshots endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ReportSnapshot, User

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.report import ReportSnapshotRead

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/snapshots", response_model=list[ReportSnapshotRead])
async def list_snapshots(
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(ReportSnapshot)
    if project_id:
        stmt = stmt.where(ReportSnapshot.project_id == uuid.UUID(project_id))
    stmt = stmt.order_by(ReportSnapshot.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
