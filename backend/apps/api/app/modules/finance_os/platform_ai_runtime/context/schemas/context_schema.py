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


class EntityCandidate(BaseModel):
    entity_type: str
    entity_id: str | None = None
    label: str | None = None
    score: float = 0.0
    match_type: str = "unknown"
    source: str = "unknown"


class ResolvedEntity(BaseModel):
    entity_type: str
    entity_id: str | None = None
    label: str | None = None
    source: str = "unknown"
    confidence: float = 0.5
    needs_clarification: bool = False
    candidates: list[EntityCandidate] = Field(default_factory=list)
    match_type: str | None = None


class EntityResolutionResult(BaseModel):
    entities: list[ResolvedEntity] = Field(default_factory=list)
    candidates: list[EntityCandidate] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    threshold: float = 0.75


class RetrievalSource(BaseModel):
    source_type: str
    tool: str | None = None
    method: str | None = None
    params: dict = Field(default_factory=dict)
    priority: int = 1
    cross_module: bool = False


class RetrievalPlan(BaseModel):
    sources: list[RetrievalSource] = Field(default_factory=list)
    query: str = ""
    module_hints: list[str] = Field(default_factory=list)
    plan_reason: str = ""
    required_modules: list[str] = Field(default_factory=list)


class ContextItemMeta(BaseModel):
    """Freshness / provenance for a retrieved unit (Wave 4)."""

    source: str = "unknown"
    timestamp: str | None = None
    version: str | None = None
    confidence: float = 0.5
    freshness: float = 1.0  # 1.0 = fresh, 0.0 = stale
    staleness_seconds: float | None = None


class ContextQuality(BaseModel):
    completeness: float = 0.0
    coverage: float = 0.0
    confidence: float = 0.0
    freshness: float = 0.0
    relevance: float = 0.0
    token_size: int = 0
    sufficient: bool = True
    missing: list[str] = Field(default_factory=list)
    action: str = "ok"  # ok | expand_retrieval | clarify


class ConversationState(BaseModel):
    """Session-scoped working memory — not long-term M27 memory."""

    current_entity: dict | None = None
    current_vendor_id: str | None = None
    current_customer_id: str | None = None
    current_period: str | None = None
    last_intent: str | None = None
    topic_stack: list[str] = Field(default_factory=list)
    turn_count: int = 0
    current_task: str | None = None
    current_goal_summary: str | None = None
    current_comparisons: list[str] = Field(default_factory=list)
    current_reports: list[str] = Field(default_factory=list)
    reasoning_chain: list[str] = Field(default_factory=list)
    last_user_utterance: str | None = None
    last_assistant_summary: str | None = None


class PlatformContext(BaseModel):
    intent: IntentResult
    entities: list[ResolvedEntity] = Field(default_factory=list)
    entity_resolution: EntityResolutionResult | None = None
    world_state: WorldState
    memory: list[dict] = Field(default_factory=list)
    graph: list[dict] = Field(default_factory=list)
    erp_facts: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict] = Field(default_factory=list)
    policies: list[dict] = Field(default_factory=list)
    workflow_state: list[dict] = Field(default_factory=list)
    approval_queue: list[dict] = Field(default_factory=list)
    recent_events: list[dict] = Field(default_factory=list)
    summaries: dict[str, str] = Field(default_factory=dict)
    working_memory: ConversationState = Field(default_factory=ConversationState)
    token_estimate: int = 0
    retrieval_trace: list[dict] = Field(default_factory=list)
    retrieval_complete: bool = True
    retrieval_failures: list[dict] = Field(default_factory=list)
    retrieval_plan: RetrievalPlan | None = None
    item_meta: list[ContextItemMeta] = Field(default_factory=list)
    quality: ContextQuality | None = None
    question: str = ""
    clarification_required: bool = False
    clarification_prompt: str | None = None
    context_cache_hit: bool = False
