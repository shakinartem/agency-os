"""ReportSnapshot model — periodic performance snapshots."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class ReportSnapshot(Base):
    """Immutable report snapshot — no updated_at."""
    __tablename__ = "report_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    # relationships
    project = relationship("Project", back_populates="report_snapshots")

    def __repr__(self) -> str:
        return f"<ReportSnapshot {self.period_start}–{self.period_end}>"
