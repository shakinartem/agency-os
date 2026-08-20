"""Auth-related schemas."""

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginResponse(BaseModel):
    authenticated: bool = True
    expires_in_seconds: int


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
