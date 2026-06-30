"""Conversation model."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import ConversationSource, ConversationStatus
from ..mixins import TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False,
    )
    source: Mapped[ConversationSource] = mapped_column(
        String(20), default=ConversationSource.telegram, nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        String(20), default=ConversationStatus.active, nullable=False, index=True,
    )
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # relationships
    project = relationship("Project", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation",
                            cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Conversation {self.id} lead={self.lead_id} [{self.status.value}]>"
