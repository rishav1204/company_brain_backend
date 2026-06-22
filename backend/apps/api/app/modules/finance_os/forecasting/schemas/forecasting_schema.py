from __future__ import annotations

from pydantic import BaseModel, Field


class ForecastRow(BaseModel):
    forecast_date: str
    forecast_value: float


class ForecastSeriesResponse(BaseModel):
    forecast_type: str
    horizon_days: int
    as_of_date: str
    confidence_score: float
    confidence_band: str
    items: list[ForecastRow] = Field(default_factory=list)
    explanation: str | None = None
    evidence: dict = Field(default_factory=dict)


class ScenarioResponse(BaseModel):
    horizon_days: int
    as_of_date: str
    scenarios: list[dict] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    as_of_date: str
    cash: dict = Field(default_factory=dict)
    collections: dict = Field(default_factory=dict)
    expenses: dict = Field(default_factory=dict)
    tax: dict = Field(default_factory=dict)
    working_capital: dict = Field(default_factory=dict)

