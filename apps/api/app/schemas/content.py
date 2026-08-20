"""Content schemas used by the Content Factory review workspace."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ContentItemCreate(BaseModel):
    project_id: str
    type: str = "post"
    status: Literal["draft", "review"] = "draft"
    title: str
    body: str | None = None
    task: str | None = None
    topic: str | None = None
    goal: str | None = None
    platforms: list[str] = Field(default_factory=list)


class ContentItemUpdate(BaseModel):
    type: str | None = None
    status: Literal["draft", "review"] | None = None
    title: str | None = None
    body: str | None = None
    hook: str | None = None
    cta: str | None = None
    hashtags: list[str] | None = None
    visual_prompt: str | None = None


class ContentItemRead(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    title: str
    body: str | None = None
    task: str | None = None
    topic: str | None = None
    goal: str | None = None
    hook: str | None = None
    cta: str | None = None
    hashtags: list[str] | None = None
    platforms: list[str] | None = None
    visual_prompt: str | None = None
    structured_json: dict[str, Any] | None = None
    research_sources: list[dict[str, Any]] | None = None
    knowledge_refs: list[dict[str, Any]] | None = None
    quality_score: float | None = None
    current_version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
