"""Initial migration — create all 13 tables (users through system_settings).

Revises: None
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_all_tables"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False,
                  server_default=sa.text("'viewer'")),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])

    # ── projects ─────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"])

    # ── leads ────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("telegram", sa.String(255), nullable=True),
        sa.Column("whatsapp", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'new'")),
        sa.Column("source", sa.String(20), nullable=False,
                  server_default=sa.text("'manual'")),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_leads_status"), "leads", ["status"])

    # ── lead_events ──────────────────────────────────────
    op.create_table(
        "lead_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index(op.f("ix_lead_events_lead_id"),
                    "lead_events", ["lead_id"])

    # ── conversations ────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source", sa.String(20), nullable=False,
                  server_default=sa.text("'telegram'")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_conversations_status"),
                    "conversations", ["status"])

    # ── conversation_messages ────────────────────────────
    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(20), nullable=False,
                  server_default=sa.text("'user'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index(op.f("ix_conversation_messages_conversation_id"),
                    "conversation_messages", ["conversation_id"])

    # ── content_items ────────────────────────────────────
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("type", sa.String(20), nullable=False,
                  server_default=sa.text("'post'")),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'draft'")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_content_items_status"),
                    "content_items", ["status"])

    # ── content_plans ────────────────────────────────────
    op.create_table(
        "content_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=True,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index(op.f("ix_content_plans_month"),
                    "content_plans", ["month"])

    # ── publications ─────────────────────────────────────
    op.create_table(
        "publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("content_items.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.String(32), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'scheduled'")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )

    # ── report_snapshots ─────────────────────────────────
    op.create_table(
        "report_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("period_start", sa.String(32), nullable=False),
        sa.Column("period_end", sa.String(32), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.String(32), nullable=False),
    )

    # ── integration_configs ──────────────────────────────
    op.create_table(
        "integration_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("health_status", sa.String(20), nullable=False,
                  server_default=sa.text("'healthy'")),
        sa.Column("last_sync_at", sa.String(32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )

    # ── integration_logs ─────────────────────────────────
    op.create_table(
        "integration_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("integration_config_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("integration_configs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index(op.f("ix_integration_logs_integration_config_id"),
                    "integration_logs", ["integration_config_id"])

    # ── system_settings ──────────────────────────────────
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_system_settings_key"),
                    "system_settings", ["key"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("integration_logs")
    op.drop_table("integration_configs")
    op.drop_table("report_snapshots")
    op.drop_table("publications")
    op.drop_table("content_plans")
    op.drop_table("content_items")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("lead_events")
    op.drop_table("leads")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("system_settings")
