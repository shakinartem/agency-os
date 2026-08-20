"""Versioned contract between Content Factory and Autoposter."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(StrictModel):
    id: str
    title: str
    url: HttpUrl
    score: float | None = Field(default=None, ge=0, le=1)


class MediaRef(StrictModel):
    asset_id: str = Field(min_length=1, max_length=120)
    type: str = "image"
    url: str
    mime_type: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class ContentVariantPayload(StrictModel):
    platform: str = Field(min_length=1, max_length=50)
    title: str | None = None
    plain_text: str
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    media: list[MediaRef] = Field(default_factory=list)


class CanonicalPayload(StrictModel):
    content_type: str = Field(min_length=1, max_length=50)
    topic: str | None = None
    goal: str | None = None
    title: str
    body: str | None = None
    hook: str | None = None
    cta: str | None = None


class QualityPayload(StrictModel):
    overall: float | None = None
    factuality: float | None = None
    brand_voice: float | None = None
    media: float | None = None


class LineagePayload(StrictModel):
    content_version: int = Field(ge=1)
    export_delivery_id: str = Field(min_length=1, max_length=100)
    generation_run_id: str | None = None
    batch_id: str | None = None
    rubric_id: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = Field(default=None, min_length=64, max_length=64)
    model: str | None = None
    model_router: dict[str, Any] = Field(default_factory=dict)
    shadow_experiment_ids: list[str] = Field(default_factory=list, max_length=50)


class ContentPackageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["content-package/1.0", "content-package/1.1"] = "content-package/1.1"
    content_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=100)
    status: str
    canonical: CanonicalPayload
    variants: list[ContentVariantPayload] = Field(min_length=1, max_length=50)
    sources: list[SourceRef] = Field(default_factory=list)
    quality: QualityPayload
    lineage: LineagePayload | None = None

    @model_validator(mode="after")
    def require_lineage_for_11(self):
        if self.schema_version == "content-package/1.1" and self.lineage is None:
            raise ValueError("content-package/1.1 requires immutable lineage")
        return self


def validate_content_package(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a package before it is persisted or sent."""
    return ContentPackageV1.model_validate(payload).model_dump(mode="json")
