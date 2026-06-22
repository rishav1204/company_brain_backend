from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineEntryOut(BaseModel):
    id: str
    object_type: str
    object_id: str
    event_type: str
    actor_id: str | None = None
    event_timestamp: str | None = None
    metadata: dict = Field(default_factory=dict)
    object_ref: str | None = None
    trace_id: str | None = None
    evidence: list[dict] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    request_id: str
    object_type: str
    object_id: str
    items: list[TimelineEntryOut]
    count: int


class EvidenceResponse(BaseModel):
    request_id: str
    object_type: str
    object_id: str
    items: list[dict]
    governance_items: list[dict] = Field(default_factory=list)


class ApprovalChainResponse(BaseModel):
    request_id: str
    workflow_id: str
    approvals: list[dict]
    steps: list[dict]
    instance: dict | None = None


class AIDecisionResponse(BaseModel):
    request_id: str
    execution_id: str
    trails: list[dict]
    execution: dict | None = None
    recommendations: list[dict] = Field(default_factory=list)
    memory_factors: list[dict] = Field(default_factory=list)


class SearchResponse(BaseModel):
    request_id: str
    items: list[dict]
    count: int
    offset: int
    limit: int


class ExploreResponse(BaseModel):
    request_id: str
    object_type: str
    object_id: str
    timeline: list[dict]
    evidence: list[dict]
    ai_decisions: list[dict]
    lineage: dict | None = None


class CopilotRequest(BaseModel):
    question: str
    object_type: str | None = None
    object_id: str | None = None


class CopilotResponse(BaseModel):
    answer: str
    sources: dict = Field(default_factory=dict)
    confidence_band: str = "review"
