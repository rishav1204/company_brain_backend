from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorldStateScreen(BaseModel):
    module: str | None = None
    route: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    title: str | None = None
    breadcrumb: str | None = None
    tab: str | None = None
    panel: str | None = None
    modal: str | None = None
    current_action: str | None = None


class WorldStateOrg(BaseModel):
    company_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    legal_entity_id: str | None = None
    fiscal_period_id: str | None = None
    fiscal_period_open: bool | None = None


class WorldState(BaseModel):
    """Platform world state — published by UI, never inferred solely by the LLM (Wave 4)."""

    screen: WorldStateScreen | None = None
    org: WorldStateOrg | None = None
    selection: dict = Field(default_factory=dict)
    filters: dict = Field(default_factory=dict)
    search: dict = Field(default_factory=dict)
    sort: dict = Field(default_factory=dict)
    active_workflows: list[dict] = Field(default_factory=list)
    pending_approvals: list[dict] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    recent_entities: list[dict] = Field(default_factory=list)
    recently_viewed: list[dict] = Field(default_factory=list)
    recent_navigation: list[dict] = Field(default_factory=list)
    selected_records: list[dict] = Field(default_factory=list)
    dashboard: dict = Field(default_factory=dict)
    current_invoice_id: str | None = None
    current_vendor_id: str | None = None
    current_customer_id: str | None = None
    current_journal_id: str | None = None
    current_po_id: str | None = None
    current_workflow_id: str | None = None
    current_approval_id: str | None = None
    updated_at: str | None = None
    # Wave 5 — operational objectives for long-running goals
    operational_objectives: list[dict] = Field(default_factory=list)
    financial_targets: dict = Field(default_factory=dict)


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
    prep_only: bool = False
    parallel_group: str | None = None


class AutonomyEnvelope(BaseModel):
    """Governance declaration for every autonomous action (Wave 5). Never mutates truth alone."""

    reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    planner_confidence: float = 0.0
    required_policy: list[str] = Field(default_factory=list)
    required_approval: bool = True
    rollback_strategy: list[dict] = Field(default_factory=list)
    affected_erp_objects: list[dict] = Field(default_factory=list)
    business_impact: str = ""
    prep_only: bool = True
    autonomy_tier: Literal["observe", "recommend", "prepare", "execute_with_approval"] = "recommend"
    max_steps: int | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    money_ceiling: float | None = None
    time_horizon: str | None = None


class PlanMetadata(BaseModel):
    confidence: float = 0.0
    confidence_band: str = "manual"
    risk_level: str = "low"
    reasoning: str = ""
    estimated_steps: int = 0
    approval_points: list[str] = Field(default_factory=list)
    rollback_strategy: list[dict] = Field(default_factory=list)
    prep_only: bool = False
    envelope: AutonomyEnvelope | None = None
    event_decision: str | None = None
    optimization_notes: list[str] = Field(default_factory=list)
    goal_memory_refs: list[str] = Field(default_factory=list)
    estimated_completion: str | None = None
    collaboration_message: str | None = None


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
    outcome: str = "unknown"
    escalate: bool = False
    partial: bool = False
    terminate_goal: bool = False


class EventPlanDecision(BaseModel):
    """Event-driven planner output — never executes (Wave 5)."""

    action: Literal[
        "ignore",
        "observe",
        "recommend",
        "start_goal",
        "resume_goal",
        "notify_user",
        "prepare_workflow",
        "approval_required",
    ] = "observe"
    event_type: str = ""
    template_key: str | None = None
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    goal_id: str | None = None
    prep_only: bool = True
    envelope: AutonomyEnvelope | None = None
    recommendation: dict | None = None
    collaboration_message: str | None = None
    notify: bool = False


class AutonomyRecommendation(BaseModel):
    recommendation_type: str
    title: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    business_impact: str = ""
    required_approvals: list[str] = Field(default_factory=list)
    estimated_benefit: str | None = None
    affected_objects: list[dict] = Field(default_factory=list)
    prep_only: bool = True
    envelope: AutonomyEnvelope | None = None


class GoalObjective(BaseModel):
    objective_id: str
    kind: Literal["business", "operational", "financial"] = "operational"
    title: str
    target: str | None = None
    metric: str | None = None
    status: str = "active"
    horizon: str | None = None
    evidence: list[str] = Field(default_factory=list)
    linked_goal_ids: list[str] = Field(default_factory=list)


class GoalProgressSnapshot(BaseModel):
    goal_id: str
    run_id: str | None = None
    current_node_id: str | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    pending_nodes: list[str] = Field(default_factory=list)
    approval_state: str | None = None
    checkpoint: str | None = None
    progress_percent: float = 0.0
    risk_level: str | None = None
    estimated_completion: str | None = None
    steps_completed: int = 0


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1)
    goal_id: str | None = None
    world_state: WorldState | None = None
    human_approved: bool = False
    selected_alternative_index: int | None = None
    prep_only: bool | None = None


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
    collaboration_message: str | None = None
    recommendations: list[dict] = Field(default_factory=list)
    envelope: AutonomyEnvelope | None = None
    progress: GoalProgressSnapshot | None = None


class ApprovalQueueItem(BaseModel):
    source: str
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
    goal_type: str = "user"
    prep_only: bool = False
    objectives: list[GoalObjective] = Field(default_factory=list)
    horizon: str | None = None


class GoalApproveRequest(BaseModel):
    approved_by: str | None = None
    comment: str | None = None


class GoalUndoRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=20)


class WorldStatePublishRequest(BaseModel):
    goal_id: str | None = None
    world_state: WorldState


class OperationalGoalRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    horizon: str = "days"
    objectives: list[GoalObjective] = Field(default_factory=list)
    financial_targets: dict = Field(default_factory=dict)
    prep_only: bool = True
    world_state: WorldState | None = None
    trigger_config: dict = Field(default_factory=dict)
