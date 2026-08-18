"""Materialized Model Router snapshots.

Revision ID: 0009_model_router_snapshots
Revises: 0008_factory_learning_loop
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_model_router_snapshots"
down_revision: str | None = "0008_factory_learning_loop"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "model_router_snapshots",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("default_model", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="stale"),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_router_snapshots_status", "model_router_snapshots", ["status"])


def downgrade() -> None:
    op.drop_index("ix_model_router_snapshots_status", table_name="model_router_snapshots")
    op.drop_table("model_router_snapshots")
