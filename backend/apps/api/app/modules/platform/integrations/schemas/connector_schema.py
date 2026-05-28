from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectorCreateRequest(BaseModel):
    connector_type: str = Field(min_length=2, max_length=32)
    provider_name: str = Field(min_length=2, max_length=64)
    config: dict = Field(default_factory=dict)
    # Credentials are accepted only on create/update, encrypted at rest, never returned back.
    credentials: dict = Field(default_factory=dict)

