"""Prompt/model shadow experiment registry.

Revision ID: 0010_prompt_experiment_registry
Revises: 0009_model_router_snapshots
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_prompt_experiment_registry"
down_revision: str | None = "0009_model_router_snapshots"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("stage_family", sa.String(length=80), nullable=False),
        sa.Column("content_types", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("sample_rate", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("min_samples", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("primary_metric", sa.String(length=80), nullable=False, server_default="judge_quality"),
        sa.Column("control_prompt_version", sa.String(length=120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.create_index("ix_prompt_experiments_project_id", "prompt_experiments", ["project_id"])
    op.create_index("ix_prompt_experiments_created_by_user_id", "prompt_experiments", ["created_by_user_id"])
    op.create_index("ix_prompt_experiments_stage_family", "prompt_experiments", ["stage_family"])
    op.create_index("ix_prompt_experiments_status", "prompt_experiments", ["status"])
    op.create_index(
        "uq_prompt_experiments_shadow_stage",
        "prompt_experiments",
        ["project_id", "stage_family"],
        unique=True,
        postgresql_where=sa.text("status = 'shadow'"),
    )

    op.create_table(
        "prompt_experiment_arms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prompt_experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=180), nullable=True),
        sa.Column("system_append", sa.Text(), nullable=True),
        sa.Column("prompt_append", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("experiment_id", "key", name="uq_prompt_experiment_arm_key"),
    )
    op.create_index("ix_prompt_experiment_arms_experiment_id", "prompt_experiment_arms", ["experiment_id"])

    op.create_table(
        "prompt_experiment_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prompt_experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("arm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prompt_experiment_arms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_step_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage_family", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("control_model", sa.String(length=180), nullable=False),
        sa.Column("candidate_model", sa.String(length=180), nullable=False),
        sa.Column("control_prompt_version", sa.String(length=120), nullable=False),
        sa.Column("candidate_prompt_version", sa.String(length=180), nullable=False),
        sa.Column("winner", sa.String(length=30), nullable=True),
        sa.Column("control_quality", sa.Float(), nullable=True),
        sa.Column("candidate_quality", sa.Float(), nullable=True),
        sa.Column("quality_delta", sa.Float(), nullable=True),
        sa.Column("candidate_latency_ms", sa.Integer(), nullable=True),
        sa.Column("candidate_cost_usd", sa.Float(), nullable=True),
        sa.Column("production_output_hash", sa.String(length=64), nullable=True),
        sa.Column("candidate_output_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("generation_step_id", name="uq_prompt_experiment_observation_step"),
        sa.UniqueConstraint("experiment_id", "run_id", "stage_family", name="uq_prompt_experiment_observation_run_stage"),
    )
    op.create_index("ix_prompt_experiment_observations_experiment_id", "prompt_experiment_observations", ["experiment_id"])
    op.create_index("ix_prompt_experiment_observations_arm_id", "prompt_experiment_observations", ["arm_id"])
    op.create_index("ix_prompt_experiment_observations_run_id", "prompt_experiment_observations", ["run_id"])
    op.create_index("ix_prompt_experiment_observations_generation_step_id", "prompt_experiment_observations", ["generation_step_id"], unique=True)
    op.create_index("ix_prompt_experiment_observations_content_item_id", "prompt_experiment_observations", ["content_item_id"])
    op.create_index("ix_prompt_experiment_observations_stage_family", "prompt_experiment_observations", ["stage_family"])
    op.create_index("ix_prompt_experiment_observations_status", "prompt_experiment_observations", ["status"])
    op.create_index("ix_prompt_experiment_observations_winner", "prompt_experiment_observations", ["winner"])


def downgrade() -> None:
    op.drop_table("prompt_experiment_observations")
    op.drop_table("prompt_experiment_arms")
    op.drop_index("uq_prompt_experiments_shadow_stage", table_name="prompt_experiments")
    op.drop_table("prompt_experiments")
