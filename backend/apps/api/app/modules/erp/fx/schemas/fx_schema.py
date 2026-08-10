from __future__ import annotations

from pydantic import BaseModel, Field


class ExchangeRateCreateRequest(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=8)
    to_currency: str = Field(default="INR", min_length=3, max_length=8)
    rate: float = Field(..., gt=0)
    rate_date: str
    source: str = "manual"
    company_id: str | None = None


class ExchangeRateUpdateRequest(BaseModel):
    rate: float | None = Field(default=None, gt=0)
    source: str | None = None


class FxRevaluationRunRequest(BaseModel):
    revaluation_date: str
    company_id: str | None = None
    fiscal_period_id: str | None = None
