"""Content item — canonical content produced by the factory."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import ContentStatus, ContentType
from ..mixins import TimestampMixin
from ._types import enum_type


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    type: Mapped[ContentType] = mapped_column(enum_type(ContentType), default=ContentType.post, nullable=False)
    status: Mapped[ContentStatus] = mapped_column(
        enum_type(ContentStatus), default=ContentStatus.draft, nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content Factory fields. The canonical item is immutable in spirit: every AI/manual
    # rewrite is appended to content_versions while these fields point at the current best version.
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    platforms: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    visual_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project = relationship("Project", back_populates="content_items")
    publications = relationship("Publication", back_populates="content_item")

    def __repr__(self) -> str:
        return f"<ContentItem {self.title!r} [{self.type.value}]>"
