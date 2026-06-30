"""IntegrationLog model — action log for integration syncs / calls."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import IntegrationAction, IntegrationActionStatus


class IntegrationLog(Base):
    """Immutable log entry for integration actions."""
    __tablename__ = "integration_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    integration_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_configs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[IntegrationAction] = mapped_column(
        String(20), nullable=False,
    )
    status: Mapped[IntegrationActionStatus] = mapped_column(
        String(20), nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    # relationships
    integration_config = relationship("IntegrationConfig", back_populates="logs")

    def __repr__(self) -> str:
        return f"<IntegrationLog {self.action.value} [{self.status.value}]>"
