"""Add AI generation lineage and metadata to rubrics.

Revises: 0004_content_research_sources
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_rubric_lineage"
down_revision: str | None = "0004_content_research_sources"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("rubrics", sa.Column("generation_run_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("rubrics", sa.Column("origin", sa.String(length=30), nullable=False, server_default="manual"))
    op.add_column("rubrics", sa.Column("metadata_json", postgresql.JSONB(), nullable=True))
    op.create_index("ix_rubrics_generation_run_id", "rubrics", ["generation_run_id"], unique=False)
    op.create_foreign_key(
        "fk_rubrics_generation_run_id_generation_runs",
        "rubrics",
        "generation_runs",
        ["generation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rubrics_generation_run_id_generation_runs", "rubrics", type_="foreignkey")
    op.drop_index("ix_rubrics_generation_run_id", table_name="rubrics")
    op.drop_column("rubrics", "metadata_json")
    op.drop_column("rubrics", "origin")
    op.drop_column("rubrics", "generation_run_id")
