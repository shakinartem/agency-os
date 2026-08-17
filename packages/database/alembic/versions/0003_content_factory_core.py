"""Add Content Factory domain tables and canonical content fields.

Revises: 0002_add_password_hash
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_content_factory_core"
down_revision: str | None = "0002_add_password_hash"
branch_labels: str | None = None
depends_on: str | None = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB()


def upgrade() -> None:
    op.add_column("content_items", sa.Column("task", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("topic", sa.String(500), nullable=True))
    op.add_column("content_items", sa.Column("goal", sa.String(255), nullable=True))
    op.add_column("content_items", sa.Column("hook", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("cta", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("hashtags", JSON, nullable=True))
    op.add_column("content_items", sa.Column("platforms", JSON, nullable=True))
    op.add_column("content_items", sa.Column("visual_prompt", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("structured_json", JSON, nullable=True))
    op.add_column("content_items", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("content_items", sa.Column("current_version", sa.Integer(), server_default="0", nullable=False))

    op.create_table(
        "brand_profiles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("audience", JSON, nullable=True),
        sa.Column("products", JSON, nullable=True),
        sa.Column("tone_of_voice", JSON, nullable=True),
        sa.Column("brand_rules", JSON, nullable=True),
        sa.Column("forbidden_claims", JSON, nullable=True),
        sa.Column("examples", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "rubrics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.String(255), nullable=True),
        sa.Column("content_types", JSON, nullable=True),
        sa.Column("platforms", JSON, nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_rubrics_project_id", "rubrics", ["project_id"])

    op.create_table(
        "generation_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("platforms", JSON, nullable=True),
        sa.Column("options", JSON, nullable=True),
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("current_stage", sa.String(80), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_generation_runs_project_id", "generation_runs", ["project_id"])
    op.create_index("ix_generation_runs_content_item_id", "generation_runs", ["content_item_id"])
    op.create_index("ix_generation_runs_status", "generation_runs", ["status"])

    op.create_table(
        "generation_steps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("run_id", UUID, sa.ForeignKey("generation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("input_json", JSON, nullable=True),
        sa.Column("output_json", JSON, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_generation_steps_run_id", "generation_steps", ["run_id"])

    op.create_table(
        "content_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("structured_json", JSON, nullable=True),
        sa.Column("created_by", sa.String(50), server_default="ai", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("content_item_id", "version", name="uq_content_version_number"),
    )
    op.create_index("ix_content_versions_content_item_id", "content_versions", ["content_item_id"])

    op.create_table(
        "content_variants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=True),
        sa.Column("hashtags", JSON, nullable=True),
        sa.Column("blocks", JSON, nullable=True),
        sa.Column("metadata_json", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_content_variants_content_item_id", "content_variants", ["content_item_id"])
    op.create_index("ix_content_variants_platform", "content_variants", ["platform"])

    op.create_table(
        "evaluations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("factuality", sa.Float(), nullable=True),
        sa.Column("brand_voice", sa.Float(), nullable=True),
        sa.Column("clarity", sa.Float(), nullable=True),
        sa.Column("hook", sa.Float(), nullable=True),
        sa.Column("usefulness", sa.Float(), nullable=True),
        sa.Column("originality", sa.Float(), nullable=True),
        sa.Column("policy_passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("notes", JSON, nullable=True),
        sa.Column("raw_json", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_evaluations_content_item_id", "evaluations", ["content_item_id"])

    op.create_table(
        "media_assets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", UUID, sa.ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(50), server_default="image", nullable=False),
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(150), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_media_assets_content_item_id", "media_assets", ["content_item_id"])

    op.create_table(
        "export_deliveries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content_item_id", UUID, sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination", sa.String(100), server_default="autoposter", nullable=False),
        sa.Column("schema_version", sa.String(50), server_default="content-package/1.0", nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_export_deliveries_content_item_id", "export_deliveries", ["content_item_id"])
    op.create_index("ix_export_deliveries_status", "export_deliveries", ["status"])


def downgrade() -> None:
    for table in [
        "export_deliveries", "media_assets", "evaluations", "content_variants",
        "content_versions", "generation_steps", "generation_runs", "rubrics", "brand_profiles",
    ]:
        op.drop_table(table)

    for column in [
        "current_version", "quality_score", "structured_json", "visual_prompt", "platforms",
        "hashtags", "cta", "hook", "goal", "topic", "task",
    ]:
        op.drop_column("content_items", column)
