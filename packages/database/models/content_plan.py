"""ContentPlan model — monthly content plans."""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class ContentPlan(Base):
    """Monthly content plan — items stored as JSONB array."""
    __tablename__ = "content_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "2026-07"
    items: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    created_at: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )

    # relationships
    project = relationship("Project", back_populates="content_plans")

    def __repr__(self) -> str:
        return f"<ContentPlan {self.month} project={self.project_id}>"
