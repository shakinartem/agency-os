"""CRUD /settings (SystemSetting key-value store)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import SystemSetting, User

from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.settings import SystemSettingCreate, SystemSettingRead, SystemSettingUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=list[SystemSettingRead])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    return result.scalars().all()


@router.get("/{key}", response_model=SystemSettingRead)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SystemSettingRead)
async def upsert_setting(
    key: str,
    body: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        setting = SystemSetting(key=key, value=body.value)
        db.add(setting)
    await db.flush()
    await db.refresh(setting)
    return setting


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Setting not found")
    await db.delete(setting)
