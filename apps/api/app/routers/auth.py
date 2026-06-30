"""Auth endpoints: login, logout, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.auth import LoginRequest, MeResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(subject=str(user.id), extra={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    # Stateless JWT — client discards the token.
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
