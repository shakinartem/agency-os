"""Add batch production, review decisions, performance snapshots and task outbox.

Revises: 0007_content_knowledge_refs
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_factory_learning_loop"
down_revision: str | None = "0007_content_knowledge_refs"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "production_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planner_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("platforms", postgresql.JSONB(), nullable=True),
        sa.Column("content_mix", postgresql.JSONB(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("strategy_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("planner_run_id", name="uq_production_batches_planner_run_id"),
    )
    op.create_index("ix_production_batches_project_id", "production_batches", ["project_id"])
    op.create_index("ix_production_batches_status", "production_batches", ["status"])

    op.create_table(
        "production_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rubric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("child_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("goal", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="planned"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("batch_id", "position", name="uq_production_batch_item_position"),
        sa.UniqueConstraint("child_run_id", name="uq_production_batch_items_child_run_id"),
    )
    op.create_index("ix_production_batch_items_batch_id", "production_batch_items", ["batch_id"])
    op.create_index("ix_production_batch_items_rubric_id", "production_batch_items", ["rubric_id"])
    op.create_index("ix_production_batch_items_status", "production_batch_items", ["status"])

    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_review_decisions_content_item_id", "review_decisions", ["content_item_id"])
    op.create_index("ix_review_decisions_user_id", "review_decisions", ["user_id"])
    op.create_index("ix_review_decisions_action", "review_decisions", ["action"])

    op.create_table(
        "performance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="autoposter"),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("external_publication_id", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source", "event_id", name="uq_performance_source_event"),
    )
    op.create_index("ix_performance_snapshots_project_id", "performance_snapshots", ["project_id"])
    op.create_index("ix_performance_snapshots_content_item_id", "performance_snapshots", ["content_item_id"])
    op.create_index("ix_performance_snapshots_external_publication_id", "performance_snapshots", ["external_publication_id"])
    op.create_index("ix_performance_snapshots_platform", "performance_snapshots", ["platform"])

    op.create_table(
        "task_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_name", sa.String(length=180), nullable=False),
        sa.Column("args_json", postgresql.JSONB(), nullable=True),
        sa.Column("kwargs_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("dedupe_key", name="uq_task_outbox_dedupe_key"),
    )
    op.create_index("ix_task_outbox_task_name", "task_outbox", ["task_name"])
    op.create_index("ix_task_outbox_status", "task_outbox", ["status"])
    op.create_index("ix_task_outbox_available_at", "task_outbox", ["available_at"])
    op.create_index("ix_task_outbox_dedupe_key", "task_outbox", ["dedupe_key"])


def downgrade() -> None:
    op.drop_index("ix_task_outbox_dedupe_key", table_name="task_outbox")
    op.drop_index("ix_task_outbox_available_at", table_name="task_outbox")
    op.drop_index("ix_task_outbox_status", table_name="task_outbox")
    op.drop_index("ix_task_outbox_task_name", table_name="task_outbox")
    op.drop_table("task_outbox")
    op.drop_index("ix_performance_snapshots_platform", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_external_publication_id", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_content_item_id", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_project_id", table_name="performance_snapshots")
    op.drop_table("performance_snapshots")
    op.drop_index("ix_review_decisions_action", table_name="review_decisions")
    op.drop_index("ix_review_decisions_user_id", table_name="review_decisions")
    op.drop_index("ix_review_decisions_content_item_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index("ix_production_batch_items_status", table_name="production_batch_items")
    op.drop_index("ix_production_batch_items_rubric_id", table_name="production_batch_items")
    op.drop_index("ix_production_batch_items_batch_id", table_name="production_batch_items")
    op.drop_table("production_batch_items")
    op.drop_index("ix_production_batches_status", table_name="production_batches")
    op.drop_index("ix_production_batches_project_id", table_name="production_batches")
    op.drop_table("production_batches")
