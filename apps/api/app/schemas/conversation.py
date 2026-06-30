"""Conversation CRUD schemas."""

from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    project_id: str
    lead_id: str
    source: str = "telegram"
    status: str = "active"
    last_message: str | None = None


class ConversationUpdate(BaseModel):
    status: str | None = None
    last_message: str | None = None
    ai_summary: str | None = None
    intent: str | None = None


class ConversationRead(BaseModel):
    id: str
    project_id: str
    lead_id: str
    source: str
    status: str
    last_message: str | None = None
    ai_summary: str | None = None
    intent: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    role: str = "user"
    content: str


class MessageRead(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str | None = None

    model_config = {"from_attributes": True}
