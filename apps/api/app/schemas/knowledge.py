"""Knowledge Base API contracts."""

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeTextCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=20)
    source_type: str = "text"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentRead(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: str
    mime_type: str | None = None
    checksum: str
    status: str
    char_count: int
    chunk_count: int
    metadata_json: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
