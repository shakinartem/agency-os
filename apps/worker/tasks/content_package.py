"""Versioned contract between Content Factory and Autoposter."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceRef(BaseModel):
    id: str
    title: str
    url: HttpUrl
    score: float | None = None


class MediaRef(BaseModel):
    asset_id: str
    type: str = "image"
    url: str
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None


class ContentVariantPayload(BaseModel):
    platform: str
    title: str | None = None
    plain_text: str
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    media: list[MediaRef] = Field(default_factory=list)


class CanonicalPayload(BaseModel):
    content_type: str
    topic: str | None = None
    goal: str | None = None
    title: str
    body: str | None = None
    hook: str | None = None
    cta: str | None = None


class QualityPayload(BaseModel):
    overall: float | None = None
    factuality: float | None = None
    brand_voice: float | None = None
    media: float | None = None


class ContentPackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["content-package/1.0"] = "content-package/1.0"
    content_id: str
    project_id: str
    status: str
    canonical: CanonicalPayload
    variants: list[ContentVariantPayload]
    sources: list[SourceRef] = Field(default_factory=list)
    quality: QualityPayload


def validate_content_package(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a package before it is persisted or sent."""
    return ContentPackageV1.model_validate(payload).model_dump(mode="json")
