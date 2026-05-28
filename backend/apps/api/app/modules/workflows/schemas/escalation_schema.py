from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EscalationOut(BaseModel):
    id: str
    workflow_instance_id: str
    escalation_type: str
    escalated_to: str | None = None
    triggered_at: datetime
    workflow_type: str | None = None


class EscalationListOut(BaseModel):
    request_id: str
    items: list[EscalationOut]
    confidence: float
    verification_status: str


class TaskOut(BaseModel):
    id: str
    task_type: str
    status: str
    assigned_to: str | None = None
    due_at: datetime | None = None
    workflow_instance_id: str
    workflow_type: str | None = None
    payload: dict = Field(default_factory=dict)


class TaskListOut(BaseModel):
    request_id: str
    items: list[TaskOut]
    confidence: float
    verification_status: str


class TaskAssignRequest(BaseModel):
    assigned_to: str
