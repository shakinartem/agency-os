"""ContentItem model — content pieces (posts, articles, videos…)."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import ContentStatus, ContentType
from ..mixins import TimestampMixin


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    type: Mapped[ContentType] = mapped_column(
        String(20), default=ContentType.post, nullable=False,
    )
    status: Mapped[ContentStatus] = mapped_column(
        String(20), default=ContentStatus.draft, nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    project = relationship("Project", back_populates="content_items")
    publications = relationship("Publication", back_populates="content_item")

    def __repr__(self) -> str:
        return f"<ContentItem {self.title!r} [{self.type.value}]>"
