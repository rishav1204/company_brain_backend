from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionCreateRequest(BaseModel):
    source_type: str = Field(min_length=2, max_length=64)
    source_reference: str | None = Field(default=None, max_length=512)
    payload: dict = Field(default_factory=dict)

