"""Publication CRUD schemas."""

from datetime import datetime

from pydantic import BaseModel


class PublicationCreate(BaseModel):
    project_id: str
    content_item_id: str | None = None
    platform: str
    scheduled_at: str | None = None
    status: str = "scheduled"


class PublicationUpdate(BaseModel):
    content_item_id: str | None = None
    platform: str | None = None
    scheduled_at: str | None = None
    status: str | None = None


class PublicationRead(BaseModel):
    id: str
    project_id: str
    content_item_id: str | None = None
    platform: str
    scheduled_at: str | None = None
    status: str
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
