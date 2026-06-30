"""Report-snapshot schemas."""

from pydantic import BaseModel


class ReportSnapshotRead(BaseModel):
    id: str
    project_id: str
    period_start: str
    period_end: str
    metrics: dict | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
