from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    workflow_instance_id: str | None = None
    workflow_type: str | None = None


class CopilotRequest(BaseModel):
    question: str
    workflow_type: str | None = None
    workflow_instance_id: str | None = None


class RecommendationActionRequest(BaseModel):
    recommendation_id: str


class OverridePredictionRequest(BaseModel):
    prediction_id: str
    predicted_value: str | None = None


class HealthResponse(BaseModel):
    health_score: float
    health_band: str
    snapshot_count: int = 0
    sla_high_risk_count: int = 0
    overload_count: int = 0
