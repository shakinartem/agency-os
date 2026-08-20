"""CRUD /users — admin only."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import AuthSession, User

from ..audit import record_audit
from ..auth import hash_password
from ..database import get_db
from ..dependencies import get_current_user, require_role
from ..schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    existing = await db.execute(select(User).where(func.lower(User.email) == str(body.email).lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already taken")

    user = User(
        email=body.email,
        name=body.name,
        role=UserRole(body.role),
        is_active=True,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    await record_audit(db, actor=current_user, action="user.create", entity_type="user", entity_id=user.id, metadata={"role": user.role.value})
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == UserRole.admin and (body.role is not None and body.role != "admin" or body.is_active is False):
        active_admins = (await db.execute(select(User.id).where(User.role == UserRole.admin, User.is_active.is_(True)))).scalars().all()
        if len(active_admins) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot demote or disable the last active admin")
    if body.email is not None:
        duplicate = await db.scalar(select(User.id).where(func.lower(User.email) == str(body.email).lower(), User.id != user.id))
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already taken")
        user.email = body.email
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = UserRole(body.role)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        # A password reset invalidates every existing browser/API session for the account.
        await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))

    await record_audit(db, actor=current_user, action="user.update", entity_type="user", entity_id=user.id, metadata={"fields": sorted(body.model_dump(exclude_unset=True))})
    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot delete the currently authenticated admin")
    if user.role == UserRole.admin and user.is_active:
        active_admins = (await db.execute(select(User.id).where(User.role == UserRole.admin, User.is_active.is_(True)))).scalars().all()
        if len(active_admins) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot delete the last active admin")
    await record_audit(db, actor=current_user, action="user.delete", entity_type="user", entity_id=user.id)
    await db.delete(user)
