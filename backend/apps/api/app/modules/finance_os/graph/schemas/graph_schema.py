from __future__ import annotations

from pydantic import BaseModel, Field


class GraphCopilotRequest(BaseModel):
    question: str
    entity_id: str | None = None


class GraphCopilotResponse(BaseModel):
    answer: str
    sources: list = Field(default_factory=list)


class GraphSearchResponse(BaseModel):
    items: list[dict]
    count: int
