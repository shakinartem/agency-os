"""Publication model — scheduled / published posts on external platforms."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import Platform, PublicationStatus
from ..mixins import TimestampMixin


class Publication(Base, TimestampMixin):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True,
    )
    platform: Mapped[Platform] = mapped_column(
        String(20), nullable=False,
    )
    scheduled_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[PublicationStatus] = mapped_column(
        String(20), default=PublicationStatus.scheduled, nullable=False, index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    project = relationship("Project", back_populates="publications")
    content_item = relationship("ContentItem", back_populates="publications")

    def __repr__(self) -> str:
        return f"<Publication {self.platform.value} [{self.status.value}]>"
