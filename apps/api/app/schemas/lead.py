"""Lead CRUD schemas."""

from datetime import datetime

from pydantic import BaseModel


class LeadCreate(BaseModel):
    project_id: str
    name: str
    phone: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None
    status: str = "new"
    source: str = "manual"
    manager_id: str | None = None


class LeadUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None
    status: str | None = None
    source: str | None = None
    manager_id: str | None = None


class LeadRead(BaseModel):
    id: str
    project_id: str
    name: str
    phone: str | None = None
    telegram: str | None = None
    whatsapp: str | None = None
    status: str
    source: str
    manager_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LeadEventRead(BaseModel):
    id: str
    lead_id: str
    type: str
    data: dict | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
