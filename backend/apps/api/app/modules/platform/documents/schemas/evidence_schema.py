from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceLinkRequest(BaseModel):
    document_id: str
    entity_type: str = Field(min_length=2, max_length=64)
    entity_id: str
    workflow_id: str | None = None
    metadata: dict = Field(default_factory=dict)
