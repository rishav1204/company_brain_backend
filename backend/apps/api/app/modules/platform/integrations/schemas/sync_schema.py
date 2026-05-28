from __future__ import annotations

from pydantic import BaseModel, Field


class SyncJobCreateRequest(BaseModel):
    connector_id: str = Field(min_length=8, max_length=64)
    sync_type: str = Field(min_length=2, max_length=64)
    metadata: dict = Field(default_factory=dict)

