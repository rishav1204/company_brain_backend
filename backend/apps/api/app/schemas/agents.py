from datetime import datetime
from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    agent_type: str
    trigger_type: str
    payload: dict = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    request_id: str
    run_id: str
    status: str
    confidence: float
    verification_status: str


class AgentRunStateResponse(BaseModel):
    request_id: str
    run_id: str
    agent_type: str
    trigger_type: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    outputs: dict = Field(default_factory=dict)
    confidence: float
    verification_status: str


class AgentApprovalRequest(BaseModel):
    approved_by: str
    comment: str | None = None
