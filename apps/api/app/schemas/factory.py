"""Pydantic contracts for Content Factory API."""

from datetime import datetime, timezone
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RunCreate(BaseModel):
    project_id: str
    task: str = Field(min_length=3)
    content_type: str = "post"
    platforms: list[str] = Field(default_factory=lambda: ["telegram"])
    use_research: bool = True
    use_knowledge: bool = True
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


class RubricGenerateRequest(BaseModel):
    project_id: str
    goal: str = Field(default="Build a balanced reusable content system", min_length=3)
    platforms: list[str] = Field(default_factory=lambda: ["telegram"])
    count: int = Field(default=8, ge=3, le=20)
    use_research: bool = True


class BatchCreate(BaseModel):
    project_id: str
    objective: str = Field(min_length=5)
    platforms: list[str] = Field(default_factory=lambda: ["telegram"])
    content_mix: dict[str, int] = Field(default_factory=lambda: {"post": 8, "article": 2})
    use_research: bool = True
    use_knowledge: bool = True
    generate_media: bool = True
    auto_export: bool = False
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_mix")
    @classmethod
    def validate_content_mix(cls, value: dict[str, int]) -> dict[str, int]:
        clean: dict[str, int] = {}
        for key, count in value.items():
            normalized = key.strip().lower()
            if not normalized or count < 0:
                raise ValueError("content_mix keys must be non-empty and counts non-negative")
            if count:
                clean[normalized] = int(count)
        total = sum(clean.values())
        if total < 1:
            raise ValueError("content_mix must request at least one item")
        if total > 100:
            raise ValueError("a single batch may contain at most 100 items")
        return clean


ReviewAction = Literal["approve", "regenerate", "manual_edit", "request_changes", "reject"]
REVIEW_REASON_CODES = {
    "generic_ai",
    "weak_hook",
    "off_brand",
    "unsupported_claim",
    "too_salesy",
    "weak_cta",
    "poor_structure",
    "duplicate_idea",
    "wrong_audience",
    "visual_mismatch",
    "other",
}


class ReviewDecisionPayload(BaseModel):
    action: ReviewAction | None = None
    reason_codes: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in value:
            code = raw.strip().lower()
            if not code:
                continue
            if code not in REVIEW_REASON_CODES:
                raise ValueError(f"unknown review reason code: {code}")
            if code not in cleaned:
                cleaned.append(code)
        return cleaned


class PerformanceIngest(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)
    source: str = Field(default="autoposter", min_length=1, max_length=50)
    content_id: str
    external_publication_id: str = Field(min_length=1, max_length=255)
    platform: str | None = Field(default=None, max_length=50)
    captured_at: datetime
    metrics: dict[str, float | int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, float | int]) -> dict[str, float | int]:
        if len(value) > 100:
            raise ValueError("metrics contains too many keys")
        cleaned: dict[str, float | int] = {}
        for key, raw in value.items():
            name = key.strip().lower()
            if not name:
                continue
            if len(name) > 100:
                raise ValueError("metric name is too long")
            number = float(raw)
            if not math.isfinite(number):
                raise ValueError(f"metric {name} must be finite")
            if number < 0:
                raise ValueError(f"metric {name} cannot be negative")
            if number > 1e15:
                raise ValueError(f"metric {name} exceeds the accepted range")
            cleaned[name] = int(number) if number.is_integer() else number
        if not cleaned:
            raise ValueError("At least one numeric metric is required")
        return cleaned

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > 128 * 1024:
            raise ValueError("metadata exceeds 128 KiB")
        return value

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if normalized > datetime.now(timezone.utc).replace(microsecond=999999):
            # Allow provider clock skew, but not arbitrarily future-dated learning events.
            from datetime import timedelta
            if normalized > datetime.now(timezone.utc) + timedelta(minutes=10):
                raise ValueError("captured_at is too far in the future")
        return normalized


class ExportRead(BaseModel):
    id: str
    content_item_id: str
    destination: str
    schema_version: str
    payload: dict[str, Any]
    status: str
    external_id: str | None = None
    error: str | None = None
