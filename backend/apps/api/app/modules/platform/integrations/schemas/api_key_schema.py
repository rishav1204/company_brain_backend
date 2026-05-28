from __future__ import annotations

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    scopes: list[str] = Field(default_factory=list)

