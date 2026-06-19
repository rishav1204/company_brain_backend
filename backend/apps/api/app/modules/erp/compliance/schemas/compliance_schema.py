from __future__ import annotations

from pydantic import BaseModel, Field


class ObligationCreate(BaseModel):
    compliance_code: str
    title: str
    due_date: str
    return_period: str | None = None
    assigned_to: str | None = None
    metadata: dict = Field(default_factory=dict)


class ObligationUpdate(BaseModel):
    title: str | None = None
    due_date: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    reason: str | None = None
    metadata: dict | None = None


class CompleteRequest(BaseModel):
    obligation_id: str


class WaiveRequest(BaseModel):
    obligation_id: str
    reason: str


class RuleUpsert(BaseModel):
    compliance_code: str
    due_day: int = 1
    month_offset: int = 1
    frequency: str = "monthly"
    reminder_offsets_days: list[int] | None = None
    escalation_levels: list[str] | None = None
    metadata: dict = Field(default_factory=dict)


class PenaltyOverride(BaseModel):
    penalty_amount: float
    interest_amount: float


class CopilotRequest(BaseModel):
    question: str


class ReadinessQuery(BaseModel):
    period: str | None = None
