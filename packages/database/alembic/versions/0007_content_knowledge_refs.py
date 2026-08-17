"""Persist internal Knowledge Base lineage on generated content.

Revises: 0006_knowledge_base
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_content_knowledge_refs"
down_revision: str | None = "0006_knowledge_base"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("knowledge_refs", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "knowledge_refs")
