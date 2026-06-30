"""LeadEvent model — tracks lead lifecycle events."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class LeadEvent(Base):
    """Immutable event log for a lead — no updated_at needed."""
    __tablename__ = "lead_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[str] = mapped_column(
        Text,  # stored as ISO-8601 string for simplicity
        nullable=False,
    )

    # relationships
    lead = relationship("Lead", back_populates="events")

    def __repr__(self) -> str:
        return f"<LeadEvent {self.type!r} lead={self.lead_id}>"
