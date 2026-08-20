"""Stable project-level learning objective.

Revision ID: 0013_project_learning_policy
Revises: 0012_exact_publication_lineage
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0013_project_learning_policy"
down_revision: str | None = "0012_exact_publication_lineage"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("learning_primary_metric", sa.String(length=80), nullable=False, server_default="views_per_publication"))
    op.add_column("projects", sa.Column("learning_exploration_share", sa.Float(), nullable=False, server_default="0.25"))
    op.add_column("projects", sa.Column("learning_min_publications", sa.Integer(), nullable=False, server_default="10"))


def downgrade() -> None:
    op.drop_column("projects", "learning_min_publications")
    op.drop_column("projects", "learning_exploration_share")
    op.drop_column("projects", "learning_primary_metric")
