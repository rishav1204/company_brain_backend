from __future__ import annotations

from pydantic import BaseModel, Field


class ReconciliationApproveRequest(BaseModel):
    ledger_entry_id: str | None = None


class ReconciliationMatchRequest(BaseModel):
    bank_transaction_ids: list[str] = Field(min_length=1)
    entity_allocations: list[dict] = Field(min_length=1)
    ledger_entry_id: str | None = None


class ReconciliationAdjustmentCreate(BaseModel):
    bank_transaction_id: str | None = None
    reconciliation_id: str | None = None
    adjustment_type: str = "bank_charge"
    amount: float = Field(gt=0)
    expense_account_id: str
    bank_account_id: str
    description: str | None = None


class ExceptionAssignRequest(BaseModel):
    assigned_to: str


class ReconciliationCopilotRequest(BaseModel):
    question: str = Field(min_length=3, max_length=512)
