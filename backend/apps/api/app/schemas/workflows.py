from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowItem(BaseModel):
    id: str
    workflow_type: str
    state: str
    owner_user_id: str | None = None
    started_at: datetime
    closed_at: datetime | None = None
    type: str | None = None
    status: str | None = None
    org_id: str | None = None
    reference_number: str | None = None
    amount: float | None = None
    metadata: dict = Field(default_factory=dict)


class WorkflowListResponse(BaseModel):
    request_id: str
    items: list[WorkflowItem]
    workflows: list[WorkflowItem] = Field(default_factory=list)
    confidence: float
    verification_status: str

class WorkflowActionRequest(BaseModel):
    action: str
    parameters: dict


class WorkflowTimelineItem(BaseModel):
    event_type: str
    occurred_at: datetime
    detail: str


class WorkflowTimelineResponse(BaseModel):
    request_id: str
    workflow_id: str
    timeline: list[WorkflowTimelineItem]
    confidence: float
    verification_status: str
