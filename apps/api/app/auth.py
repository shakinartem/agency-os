"""JWT token helpers + password hashing."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    """Create a signed JWT with an expiry claim."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire, **(extra or {})}
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Return the payload of a valid token, or raise on expiry / invalid signature."""
    try:
        return jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])
    except JWTError:
        raise ValueError("Invalid or expired token")
