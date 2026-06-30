"""Add password_hash column to users table.

Revises: 0001_create_all_tables
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_password_hash"
down_revision: str | None = "0001_create_all_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
