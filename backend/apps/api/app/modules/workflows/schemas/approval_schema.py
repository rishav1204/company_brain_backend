from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalOut(BaseModel):
    id: str
    workflow_instance_id: str
    workflow_step_id: str | None = None
    decision: str
    level: int = 1
    workflow_type: str | None = None
    owner_user_id: str | None = None
    created_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class ApprovalDecideRequest(BaseModel):
    decision: str
    reason: str | None = None
    delegate_to: str | None = None
    idempotency_key: str | None = None


class ApprovalListOut(BaseModel):
    request_id: str
    items: list[ApprovalOut]
    confidence: float
    verification_status: str
