from __future__ import annotations

from pydantic import BaseModel, Field


class PaginatedLines(BaseModel):
    items: list[dict] = Field(default_factory=list)
    next_cursor: str | None = None


class TrialBalanceResponse(BaseModel):
    fiscal_period_id: str
    totals: dict
    balanced: bool
    lines: list[dict]
    next_cursor: str | None = None
    refreshed_at: str | None = None


class StatementResponse(BaseModel):
    fiscal_period_id: str
    sections: list[dict]
    refreshed_at: str | None = None
    meta: dict = Field(default_factory=dict)


class AgingReportResponse(BaseModel):
    as_of_date: str
    totals: dict
    lines: list[dict]
    next_cursor: str | None = None
    refreshed_at: str | None = None


class CashFlowResponse(BaseModel):
    status: str = "completed"
    sections: list = Field(default_factory=list)


class TaxSummaryResponse(BaseModel):
    return_period: str
    type_value: str
    payload: dict
    refreshed_at: str | None = None


class ExportRequest(BaseModel):
    report_type: str
    format: str = "csv"
    filters: dict = Field(default_factory=dict)


class ExportRunResponse(BaseModel):
    run_id: str
    status: str
    report_type: str


class ExportStatusResponse(BaseModel):
    run_id: str
    status: str
    report_type: str
    file_ref: str | None = None
    error_message: str | None = None
