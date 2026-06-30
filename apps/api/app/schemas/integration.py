"""Integration-config schemas."""

from datetime import datetime

from pydantic import BaseModel


class IntegrationConfigCreate(BaseModel):
    project_id: str
    service_name: str
    enabled: bool = True
    base_url: str | None = None
    api_key: str | None = None


class IntegrationConfigUpdate(BaseModel):
    enabled: bool | None = None
    base_url: str | None = None
    api_key: str | None = None
    health_status: str | None = None


class IntegrationConfigRead(BaseModel):
    id: str
    project_id: str
    service_name: str
    enabled: bool
    base_url: str | None = None
    health_status: str
    last_sync_at: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class IntegrationLogRead(BaseModel):
    id: str
    integration_config_id: str
    action: str
    status: str
    payload: dict | None = None
    error: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
