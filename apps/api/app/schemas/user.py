"""User CRUD schemas with production-safe validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

UserRoleValue = Literal["admin", "manager", "viewer"]


class EmailNormalizedModel(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def normalize_email(cls, value):
        return str(value).strip().lower() if value is not None else None


class UserCreate(EmailNormalizedModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=512)
    role: UserRoleValue = "viewer"


class UserUpdate(EmailNormalizedModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=12, max_length=512)
    role: UserRoleValue | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
