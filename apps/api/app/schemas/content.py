"""Content-item CRUD schemas."""

from datetime import datetime

from pydantic import BaseModel


class ContentItemCreate(BaseModel):
    project_id: str
    type: str = "post"
    status: str = "draft"
    title: str
    body: str | None = None


class ContentItemUpdate(BaseModel):
    type: str | None = None
    status: str | None = None
    title: str | None = None
    body: str | None = None


class ContentItemRead(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    title: str
    body: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ContentPlanRead(BaseModel):
    id: str
    project_id: str
    month: str
    items: list | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
