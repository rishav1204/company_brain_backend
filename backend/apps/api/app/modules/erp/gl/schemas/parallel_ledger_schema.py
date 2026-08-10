from __future__ import annotations

from pydantic import BaseModel, Field


class ParallelLedgerCreateRequest(BaseModel):
    ledger_code: str = Field(..., min_length=1, max_length=64)
    ledger_name: str = Field(..., min_length=1, max_length=256)
    accounting_standard: str = "IFRS"
    company_id: str | None = None


class MirrorJournalRequest(BaseModel):
    journal_id: str


class MirrorBatchRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
