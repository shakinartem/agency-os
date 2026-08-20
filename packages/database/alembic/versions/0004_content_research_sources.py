"""Persist research provenance on canonical content items.

Revises: 0003_content_factory_core
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_content_research_sources"
down_revision: str | None = "0003_content_factory_core"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("research_sources", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_items", "research_sources")
