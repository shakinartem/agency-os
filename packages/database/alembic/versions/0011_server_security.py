"""Server security primitives: project memberships and revocable sessions.

Revision ID: 0011_server_security
Revises: 0010_prompt_experiment_registry
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_server_security"
down_revision: str | None = "0010_prompt_experiment_registry"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Application normalizes emails; the DB constraint closes race conditions and case variants.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (lower(email))")
    op.create_table(
        "project_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column("capabilities", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])
    op.create_index("ix_project_memberships_user_id", "project_memberships", ["user_id"])
    op.create_index("ix_project_memberships_role", "project_memberships", ["role"])

    # Preserve operator access without carrying the old global-viewer IDOR forward.
    # Admins remain global break-glass users; managers receive explicit editor membership.
    # Viewers must be assigned to projects deliberately after migration.
    op.execute(
        """
        INSERT INTO project_memberships(id, project_id, user_id, role, capabilities, created_at, updated_at)
        SELECT md5(random()::text || clock_timestamp()::text || p.id::text || u.id::text)::uuid, p.id, u.id,
               CASE
                 WHEN u.role::text = 'admin' THEN 'owner'
                 WHEN u.role::text = 'manager' THEN 'editor'
                 ELSE 'viewer'
               END,
               '[]'::jsonb, now(), now()
        FROM projects p CROSS JOIN users u
        WHERE u.is_active = true AND u.role::text IN ('admin', 'manager')
        ON CONFLICT(project_id, user_id) DO NOTHING
        """
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_table("project_memberships")
    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
