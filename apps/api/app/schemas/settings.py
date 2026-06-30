"""System-setting schemas."""

from datetime import datetime

from pydantic import BaseModel


class SystemSettingCreate(BaseModel):
    key: str
    value: str | None = None


class SystemSettingUpdate(BaseModel):
    value: str | None = None


class SystemSettingRead(BaseModel):
    id: str
    key: str
    value: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
