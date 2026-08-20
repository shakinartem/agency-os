"""Exact publication lineage on downstream performance snapshots.

Revision ID: 0012_exact_publication_lineage
Revises: 0011_server_security
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_exact_publication_lineage"
down_revision: str | None = "0011_server_security"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("performance_snapshots", sa.Column("content_version", sa.Integer(), nullable=True))
    op.add_column("performance_snapshots", sa.Column("export_delivery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("export_deliveries.id", ondelete="SET NULL"), nullable=True))
    op.add_column("performance_snapshots", sa.Column("payload_sha256", sa.String(length=64), nullable=True))
    op.add_column("performance_snapshots", sa.Column("generation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True))
    op.add_column("performance_snapshots", sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("production_batches.id", ondelete="SET NULL"), nullable=True))
    op.add_column("performance_snapshots", sa.Column("rubric_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True))
    op.add_column("performance_snapshots", sa.Column("prompt_version", sa.String(length=180), nullable=True))
    op.add_column("performance_snapshots", sa.Column("prompt_hash", sa.String(length=64), nullable=True))
    op.add_column("performance_snapshots", sa.Column("model", sa.String(length=180), nullable=True))
    op.add_column("performance_snapshots", sa.Column("model_router", postgresql.JSONB(), nullable=True))
    op.create_index("ix_performance_snapshots_export_delivery_id", "performance_snapshots", ["export_delivery_id"])
    op.create_index("ix_performance_snapshots_payload_sha256", "performance_snapshots", ["payload_sha256"])
    op.create_index("ix_performance_snapshots_generation_run_id", "performance_snapshots", ["generation_run_id"])
    op.create_index("ix_performance_snapshots_batch_id", "performance_snapshots", ["batch_id"])
    op.create_index("ix_performance_snapshots_rubric_id", "performance_snapshots", ["rubric_id"])
    op.create_index("ix_performance_snapshots_prompt_hash", "performance_snapshots", ["prompt_hash"])
    op.create_index("ix_performance_snapshots_model", "performance_snapshots", ["model"])


def downgrade() -> None:
    for name in [
        "ix_performance_snapshots_model", "ix_performance_snapshots_prompt_hash", "ix_performance_snapshots_rubric_id",
        "ix_performance_snapshots_batch_id", "ix_performance_snapshots_generation_run_id", "ix_performance_snapshots_payload_sha256",
        "ix_performance_snapshots_export_delivery_id",
    ]:
        op.drop_index(name, table_name="performance_snapshots")
    for column in ["model_router", "model", "prompt_hash", "prompt_version", "rubric_id", "batch_id", "generation_run_id", "payload_sha256", "export_delivery_id", "content_version"]:
        op.drop_column("performance_snapshots", column)
