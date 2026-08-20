"""Password hashing and revocable opaque session helpers."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuthSession

from .config import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def privacy_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hmac.new(config.secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


async def create_session(
    db: AsyncSession,
    *,
    user_id,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    # Opportunistic bounded cleanup keeps the session table from growing forever without
    # requiring another scheduler just for authentication housekeeping.
    await db.execute(delete(AuthSession).where(AuthSession.expires_at < now - timedelta(days=7)))
    row = AuthSession(
        user_id=user_id,
        token_hash=session_token_hash(token),
        expires_at=now + timedelta(minutes=max(5, config.session_ttl_minutes)),
        last_seen_at=now,
        client_ip_hash=privacy_hash(client_ip),
        user_agent_hash=privacy_hash(user_agent),
    )
    db.add(row)
    await db.flush()
    return token, row


async def resolve_session(db: AsyncSession, token: str) -> AuthSession | None:
    now = datetime.now(timezone.utc)
    row = await db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == session_token_hash(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if row is None:
        return None
    # Touch at most every five minutes to avoid a write on every request.
    if row.last_seen_at is None or (now - row.last_seen_at).total_seconds() >= 300:
        row.last_seen_at = now
        await db.flush()
    return row


async def revoke_session(db: AsyncSession, token: str) -> bool:
    row = await db.scalar(select(AuthSession).where(AuthSession.token_hash == session_token_hash(token)))
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return True
