from __future__ import annotations

from pydantic import BaseModel, Field


class FiscalYearCreateRequest(BaseModel):
    fiscal_year_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    company_id: str | None = None
    set_current: bool = True


class FiscalPeriodCreateRequest(BaseModel):
    period_name: str
    start_date: str
    end_date: str
    fiscal_year_id: str | None = None
    period_number: int | None = None
    company_id: str | None = None


class ChecklistCompleteRequest(BaseModel):
    check_name: str


class ReopenRequest(BaseModel):
    reason: str = Field(min_length=10)


class YearEndRequest(BaseModel):
    fiscal_year_id: str
    retained_earnings_account_id: str | None = None
