from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowDefinitionOut(BaseModel):
    id: str
    workflow_key: str
    name: str
    version: int
    is_active: bool
    created_at: datetime | None = None


class WorkflowInstanceOut(BaseModel):
    id: str
    workflow_type: str
    status: str
    state: str | None = None
    owner_user_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    priority: str = "normal"
    metadata: dict = Field(default_factory=dict)
    legacy_workflow_id: str | None = None


class WorkflowListOut(BaseModel):
    request_id: str
    items: list[WorkflowInstanceOut]
    workflows: list[WorkflowInstanceOut] = Field(default_factory=list)
    confidence: float
    verification_status: str


class WorkflowStartRequest(BaseModel):
    workflow_key: str | None = None
    workflow_type: str | None = None
    entity_type: str = "workflow"
    entity_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    amount: float | None = None


class WorkflowTransitionRequest(BaseModel):
    target_status: str
    reason: str | None = None
    parameters: dict = Field(default_factory=dict)


class WorkflowStepOut(BaseModel):
    id: str
    step_key: str
    step_type: str
    status: str
    assigned_to: str | None = None
    due_at: datetime | None = None


class WorkflowDetailOut(BaseModel):
    request_id: str
    instance: WorkflowInstanceOut
    steps: list[WorkflowStepOut]
    confidence: float
    verification_status: str
