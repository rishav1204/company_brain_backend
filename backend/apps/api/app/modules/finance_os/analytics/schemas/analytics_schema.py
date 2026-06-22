from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardResponse(BaseModel):
    snapshot_date: str | None = None
    refreshed_at: str | None = None
    widgets: dict = Field(default_factory=dict)
    trends: list = Field(default_factory=list)
    top_risks: list = Field(default_factory=list)
    top_opportunities: list = Field(default_factory=list)
    anomalies: list = Field(default_factory=list)


class CopilotRequest(BaseModel):
    question: str


class CopilotResponse(BaseModel):
    answer: str
    sources: dict = Field(default_factory=dict)
    confidence_band: str | None = None
