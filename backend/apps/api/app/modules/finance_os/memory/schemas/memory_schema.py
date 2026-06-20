from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryWriteRequest(BaseModel):
    memory_type: str
    title: str
    content: str
    entity_type: str | None = None
    entity_id: str | None = None
    importance_score: float = Field(default=60.0, ge=0, le=100)
    ttl_policy: str | None = None
    references: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class MemorySearchResponse(BaseModel):
    items: list[dict]
    query: str
    count: int


class MemoryCopilotRequest(BaseModel):
    question: str
    memory_type: str | None = None


class MemoryCopilotResponse(BaseModel):
    answer: str
    sources: list = Field(default_factory=list)


class MemorySummaryResponse(BaseModel):
    categories: list[dict]
    generated_at: str


class MemoryInsightsResponse(BaseModel):
    patterns: list[dict]
    top_vendor_behaviors: list[dict]
    risk_signals: list[dict]
    total_active: int


class MemoryCorrectionRequest(BaseModel):
    title: str | None = None
    content: str | None = None
