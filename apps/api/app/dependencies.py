"""FastAPI dependencies: current-user extraction and global role guard."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import UserRole
from database.models import User

from .auth import resolve_session
from .config import config
from .database import get_db

bearer = HTTPBearer(auto_error=False)


def request_session_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    cookie = request.cookies.get(config.session_cookie_name)
    if cookie:
        return cookie
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request_session_token(request, credentials)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    session = await resolve_session(db, token)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(*roles: UserRole):
    """Global role guard. Project operations should additionally use project capabilities."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' not in {[r.value for r in roles]}",
            )
        return current_user
    return role_checker
