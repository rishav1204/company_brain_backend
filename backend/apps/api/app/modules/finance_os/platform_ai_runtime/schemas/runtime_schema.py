from __future__ import annotations

from pydantic import BaseModel, Field


class WorldStateScreen(BaseModel):
    module: str | None = None
    route: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


class WorldStateOrg(BaseModel):
    company_id: str | None = None
    branch_id: str | None = None
    fiscal_period_id: str | None = None
    fiscal_period_open: bool | None = None


class WorldState(BaseModel):
    screen: WorldStateScreen | None = None
    org: WorldStateOrg | None = None
    selection: dict = Field(default_factory=dict)
    active_workflows: list[dict] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    recent_entities: list[dict] = Field(default_factory=list)


class GraphNodeSpec(BaseModel):
    id: str
    tool: str
    method: str
    params: dict = Field(default_factory=dict)
    label: str = ""
    requires_approval: bool = False
    compensation_tool: str | None = None
    status: str = "pending"
    depends_on: list[str] = Field(default_factory=list)


class PlanMetadata(BaseModel):
    confidence: float = 0.0
    confidence_band: str = "manual"
    risk_level: str = "low"
    reasoning: str = ""
    estimated_steps: int = 0
    approval_points: list[str] = Field(default_factory=list)
    rollback_strategy: list[dict] = Field(default_factory=list)


class ObservationResult(BaseModel):
    node_id: str
    tool: str
    method: str
    status: str
    success: bool = False
    retryable: bool = False
    blocked: bool = False
    reason: str | None = None
    facts: dict = Field(default_factory=dict)
    alternatives: list[dict] = Field(default_factory=list)
    raw_result: dict = Field(default_factory=dict)


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1)
    goal_id: str | None = None
    world_state: WorldState | None = None
    human_approved: bool = False
    selected_alternative_index: int | None = None


class CopilotChatResponse(BaseModel):
    goal_id: str
    goal_run_id: str
    status: str
    assistant_message: str
    mode: str
    plan: PlanMetadata | None = None
    graph_nodes: list[GraphNodeSpec] = Field(default_factory=list)
    observations: list[ObservationResult] = Field(default_factory=list)
    approval_required: bool = False
    progress_percent: float = 0.0
    pending_approval_nodes: list[str] = Field(default_factory=list)
    rollback_chain: list[dict] = Field(default_factory=list)
    sources: dict = Field(default_factory=dict)
    context_summary: dict | None = None


class ApprovalQueueItem(BaseModel):
    source: str  # m38 | m29
    goal_id: str | None = None
    goal_run_id: str | None = None
    execution_id: str | None = None
    title: str
    status: str
    current_node_id: str | None = None
    risk_level: str | None = None
    created_at: str | None = None


class GoalAlternativeRequest(BaseModel):
    alternative_index: int = Field(ge=0)
    approved_by: str | None = None


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    trigger_type: str = "api"
    world_state: WorldState | None = None
    human_approved: bool = False


class GoalApproveRequest(BaseModel):
    approved_by: str | None = None
    comment: str | None = None


class GoalUndoRequest(BaseModel):
    steps: int = 1
