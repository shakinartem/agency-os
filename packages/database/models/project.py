"""Project model."""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..mixins import TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    leads = relationship("Lead", back_populates="project")
    conversations = relationship("Conversation", back_populates="project")
    content_items = relationship("ContentItem", back_populates="project")
    content_plans = relationship("ContentPlan", back_populates="project")
    publications = relationship("Publication", back_populates="project")
    report_snapshots = relationship("ReportSnapshot", back_populates="project")
    integration_configs = relationship("IntegrationConfig", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project {self.slug!r}>"
