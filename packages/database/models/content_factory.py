"""Content Factory domain models.

These tables intentionally coexist with the legacy Agency OS tables. Runtime code uses
these models; destructive cleanup of the old CRM/reporting tables is deferred until the
new production flow is verified in deployment.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..enums import ExportStatus, GenerationRunStatus, GenerationStepStatus, MediaStatus
from ..mixins import TimestampMixin
from ._types import enum_type


class BrandProfile(Base, TimestampMixin):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    products: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    tone_of_voice: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    brand_rules: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    forbidden_claims: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)


class Rubric(Base, TimestampMixin):
    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_types: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    platforms: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    origin: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True, index=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="post", nullable=False)
    platforms: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    status: Mapped[GenerationRunStatus] = mapped_column(enum_type(GenerationRunStatus), default=GenerationRunStatus.queued, nullable=False, index=True)
    current_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class GenerationStep(Base, TimestampMixin):
    __tablename__ = "generation_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[GenerationStepStatus] = mapped_column(enum_type(GenerationStepStatus), default=GenerationStepStatus.queued, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContentVersion(Base, TimestampMixin):
    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    created_by: Mapped[str] = mapped_column(String(50), default="ai", nullable=False)


class ContentVariant(Base, TimestampMixin):
    __tablename__ = "content_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    blocks: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    factuality: Mapped[float | None] = mapped_column(Float, nullable=True)
    brand_voice: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    hook: Mapped[float | None] = mapped_column(Float, nullable=True)
    usefulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    originality: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="image", nullable=False)
    status: Mapped[MediaStatus] = mapped_column(enum_type(MediaStatus), default=MediaStatus.queued, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)


class ExportDelivery(Base, TimestampMixin):
    __tablename__ = "export_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(100), default="autoposter", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), default="content-package/1.0", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[ExportStatus] = mapped_column(enum_type(ExportStatus), default=ExportStatus.queued, nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
