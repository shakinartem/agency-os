"""IntegrationConfig model — per-project external service connections."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..enums import IntegrationHealth
from ..mixins import TimestampMixin
from ._types import enum_type


class IntegrationConfig(Base, TimestampMixin):
    __tablename__ = "integration_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted in production
    health_status: Mapped[IntegrationHealth] = mapped_column(
        enum_type(IntegrationHealth), default=IntegrationHealth.healthy, nullable=False,
    )
    last_sync_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    project = relationship("Project", back_populates="integration_configs")
    logs = relationship("IntegrationLog", back_populates="integration_config",
                        cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<IntegrationConfig {self.service_name!r} [{self.health_status.value}]>"
