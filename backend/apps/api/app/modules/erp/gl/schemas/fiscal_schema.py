from __future__ import annotations

from pydantic import BaseModel, Field


class FiscalPeriodCreateRequest(BaseModel):
    period_name: str = Field(min_length=2, max_length=128)
    start_date: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD
    end_date: str = Field(min_length=10, max_length=10)
    company_id: str | None = None

