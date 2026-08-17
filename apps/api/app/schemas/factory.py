"""Pydantic contracts for Content Factory API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    project_id: str
    task: str = Field(min_length=3)
    content_type: str = "post"
    platforms: list[str] = Field(default_factory=lambda: ["telegram"])
    use_research: bool = True
    generate_media: bool = True
    auto_export: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


class RunRead(BaseModel):
    id: str
    project_id: str
    content_item_id: str | None = None
    task: str
    content_type: str
    platforms: list[str] | None = None
    options: dict[str, Any] | None = None
    status: str
    current_stage: str | None = None
    quality_score: float | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class BrandProfileUpsert(BaseModel):
    positioning: str | None = None
    audience: dict[str, Any] = Field(default_factory=dict)
    products: list[Any] = Field(default_factory=list)
    tone_of_voice: dict[str, Any] = Field(default_factory=dict)
    brand_rules: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    examples: list[Any] = Field(default_factory=list)


class RubricCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    goal: str | None = None
    content_types: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)


class ExportRead(BaseModel):
    id: str
    content_item_id: str
    destination: str
    schema_version: str
    payload: dict[str, Any]
    status: str
    external_id: str | None = None
    error: str | None = None
