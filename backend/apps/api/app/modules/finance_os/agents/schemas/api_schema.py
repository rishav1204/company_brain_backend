from __future__ import annotations

from pydantic import BaseModel, Field


class FinanceAgentRunRequest(BaseModel):
    agent_type: str
    trigger_type: str = "api"
    payload: dict = Field(default_factory=dict)


class FinanceAgentRunResponse(BaseModel):
    execution_id: str | None = None
    platform_run_id: str | None = None
    status: str
    confidence: float
    confidence_band: str
    verification_status: str = "policy_checked"
    recommendations: list[dict] = Field(default_factory=list)


class WorkflowLaunchRequest(BaseModel):
    recommendation_id: str
    workflow_key: str | None = None


class AgentCatalogItem(BaseModel):
    agent_name: str
    aliases: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    trigger_events: list[str] = Field(default_factory=list)
