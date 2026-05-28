from __future__ import annotations

from pydantic import BaseModel, Field


class LedgerPostLine(BaseModel):
    account_id: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    currency_code: str = Field(default="INR", max_length=8)
    exchange_rate: float = 1.0
    entry_type: str = Field(default="journal", max_length=32)
    journal_id: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    cost_center_id: str | None = None


class LedgerPostRequest(BaseModel):
    posting_date: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD
    company_id: str | None = None
    lines: list[LedgerPostLine] = Field(default_factory=list, min_length=2, max_length=500)

