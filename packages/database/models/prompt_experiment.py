"""Prompt/model experiment registry for isolated shadow evidence."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..mixins import TimestampMixin


class PromptExperiment(Base, TimestampMixin):
    __tablename__ = "prompt_experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    content_types: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    sample_rate: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    min_samples: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(80), default="judge_quality", nullable=False)
    control_prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)


class PromptExperimentArm(Base, TimestampMixin):
    __tablename__ = "prompt_experiment_arms"
    __table_args__ = (UniqueConstraint("experiment_id", "key", name="uq_prompt_experiment_arm_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str | None] = mapped_column(String(180), nullable=True)
    system_append: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_append: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)


class PromptExperimentObservation(Base, TimestampMixin):
    __tablename__ = "prompt_experiment_observations"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id",
            "run_id",
            "stage_family",
            name="uq_prompt_experiment_observation_run_stage",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    arm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_experiment_arms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generation_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("generation_steps.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage_family: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    control_model: Mapped[str] = mapped_column(String(180), nullable=False)
    candidate_model: Mapped[str] = mapped_column(String(180), nullable=False)
    control_prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    candidate_prompt_version: Mapped[str] = mapped_column(String(180), nullable=False)
    winner: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    control_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    production_output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
