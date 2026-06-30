"""Project CRUD schemas."""

from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    slug: str
    status: str = "active"
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    status: str | None = None
    description: str | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
