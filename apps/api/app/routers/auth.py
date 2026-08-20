"""Auth endpoints using revocable HttpOnly sessions."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User

from ..audit import record_audit
from ..auth import create_session, revoke_session, verify_password
from ..config import config
from ..database import get_db
from ..dependencies import bearer, get_current_user, request_session_token
from ..schemas.auth import LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=config.session_cookie_name,
        value=token,
        max_age=max(300, config.session_ttl_minutes * 60),
        httponly=True,
        secure=config.session_cookie_secure,
        samesite=config.session_cookie_samesite,
        path="/",
    )


async def _rate_limit_login(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    subject = hashlib.sha256(f"{ip}|{email.strip().lower()}".encode()).hexdigest()[:32]
    key = f"content-factory:login:{subject}"
    try:
        redis = Redis.from_url(config.redis_url, decode_responses=True)
        attempts = await redis.incr(key)
        if attempts == 1:
            await redis.expire(key, max(60, config.login_rate_limit_window_seconds))
        await redis.aclose()
        if attempts > max(1, config.login_rate_limit_attempts):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")
    except HTTPException:
        raise
    except Exception as exc:
        # Redis is part of the authentication safety boundary in production. Failing closed
        # is preferable to silently disabling brute-force protection.
        if config.is_production:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication temporarily unavailable") from exc
    return key


async def _clear_rate_limit(key: str) -> None:
    try:
        redis = Redis.from_url(config.redis_url, decode_responses=True)
        await redis.delete(key)
        await redis.aclose()
    except Exception:
        pass


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    key = await _rate_limit_login(request, body.email)
    result = await db.execute(select(User).where(func.lower(User.email) == str(body.email).lower()))
    user = result.scalar_one_or_none()
    # Keep the failure response uniform to avoid account enumeration.
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, _ = await create_session(
        db,
        user_id=user.id,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _cookie(response, token)
    await record_audit(db, actor=user, action="auth.login", entity_type="user", entity_id=user.id, metadata={"session_transport": "http_only_cookie"})
    await _clear_rate_limit(key)
    return LoginResponse(expires_in_seconds=max(300, config.session_ttl_minutes * 60))


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    credentials=Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    token = request_session_token(request, credentials)
    if token:
        await revoke_session(db, token)
    response.delete_cookie(config.session_cookie_name, path="/")
    return Response(status_code=204, headers=response.headers)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
