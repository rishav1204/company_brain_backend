from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState

IntentType = Literal["read", "action", "workflow", "analysis", "mixed"]


class IntentResult(BaseModel):
    intent: IntentType = "read"
    confidence: float = 0.5
    sub_intents: list[str] = Field(default_factory=list)
    suggested_modules: list[str] = Field(default_factory=list)


class ResolvedEntity(BaseModel):
    entity_type: str
    entity_id: str | None = None
    label: str | None = None
    source: str = "unknown"
    confidence: float = 0.5


class RetrievalSource(BaseModel):
    source_type: str
    tool: str | None = None
    method: str | None = None
    params: dict = Field(default_factory=dict)
    priority: int = 1


class RetrievalPlan(BaseModel):
    sources: list[RetrievalSource] = Field(default_factory=list)
    query: str = ""
    module_hints: list[str] = Field(default_factory=list)


class ConversationState(BaseModel):
    current_entity: dict | None = None
    current_vendor_id: str | None = None
    current_period: str | None = None
    last_intent: str | None = None
    topic_stack: list[str] = Field(default_factory=list)
    turn_count: int = 0


class PlatformContext(BaseModel):
    intent: IntentResult
    entities: list[ResolvedEntity] = Field(default_factory=list)
    world_state: WorldState
    memory: list[dict] = Field(default_factory=list)
    graph: list[dict] = Field(default_factory=list)
    erp_facts: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict] = Field(default_factory=list)
    policies: list[dict] = Field(default_factory=list)
    summaries: dict[str, str] = Field(default_factory=dict)
    working_memory: ConversationState = Field(default_factory=ConversationState)
    token_estimate: int = 0
    retrieval_trace: list[dict] = Field(default_factory=list)
    question: str = ""
