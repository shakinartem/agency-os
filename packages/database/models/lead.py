"""Lead model."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import LeadSource, LeadStatus
from ..mixins import TimestampMixin


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        String(20), default=LeadStatus.new, nullable=False, index=True,
    )
    source: Mapped[LeadSource] = mapped_column(
        String(20), default=LeadSource.manual, nullable=False,
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # relationships
    project = relationship("Project", back_populates="leads")
    manager = relationship("User", back_populates="leads", foreign_keys=[manager_id])
    events = relationship("LeadEvent", back_populates="lead", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="lead")

    def __repr__(self) -> str:
        return f"<Lead {self.name!r} [{self.status.value}]>"
