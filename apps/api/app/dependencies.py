"""FastAPI dependencies: current-user extraction & role guard."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.enums import UserRole

from .auth import decode_access_token
from .database import get_db

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the bearer token, load and return the User from DB."""
    payload = decode_access_token(credentials.credentials)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        uid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid user id in token")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(*roles: UserRole):
    """Dependency factory: return a dependency that checks user role."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' not in {[r.value for r in roles]}",
            )
        return current_user
    return role_checker
