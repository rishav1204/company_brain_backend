from datetime import datetime

from pydantic import BaseModel, Field


class QAGoldExampleCreateRequest(BaseModel):
    org_scope: str = "tenant"
    question: str
    expected_answer: str
    expected_citations: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class QAGoldExampleItem(BaseModel):
    id: str
    org_scope: str
    question: str
    expected_answer: str
    expected_citations: list[dict]
    tags: list[str]
    created_at: datetime


class RetrievalJudgmentCreateRequest(BaseModel):
    query: str
    candidate_ref: str
    relevance_label: int = Field(ge=0, le=3)
    judged_by: str


class RetrievalJudgmentItem(BaseModel):
    id: str
    query: str
    candidate_ref: str
    relevance_label: int
    judged_by: str
    created_at: datetime


class SafetyEventCreateRequest(BaseModel):
    event_type: str
    severity: str
    request_id: str | None = None
    details: dict = Field(default_factory=dict)


class FeedbackEventCreateRequest(BaseModel):
    event_type: str
    payload_jsonb: dict = Field(default_factory=dict)
    created_by: str


class EvalRunStartRequest(BaseModel):
    run_type: str


class EvalRunItem(BaseModel):
    id: str
    run_type: str
    status: str
    metrics_jsonb: dict
    started_at: datetime
    completed_at: datetime | None = None


class GovernanceCycleStartRequest(BaseModel):
    candidate_version: str


class GovernanceCycleItem(BaseModel):
    id: str
    candidate_version: str
    status: str
    promotion_decision: str
    canary_percent: int
    metrics_jsonb: dict
    created_by: str
    created_at: datetime
    updated_at: datetime


class LabelingTaskItem(BaseModel):
    id: str
    feedback_event_id: str | None = None
    triage_category: str
    status: str
    payload_jsonb: dict
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class CanaryAdvanceRequest(BaseModel):
    canary_percent: int = Field(ge=0, le=100)


class GovernanceRollbackRequest(BaseModel):
    reason: str
