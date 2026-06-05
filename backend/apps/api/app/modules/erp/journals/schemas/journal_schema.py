from __future__ import annotations

from pydantic import BaseModel, Field


class JournalLineInput(BaseModel):
    account_id: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    line_description: str | None = None
    cost_center_id: str | None = None
    tax_code: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None


class JournalCreateRequest(BaseModel):
    journal_type: str = Field(default="general", max_length=32)
    posting_date: str = Field(min_length=10, max_length=10)
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    currency_code: str = Field(default="INR", max_length=8)
    exchange_rate: float = 1.0
    company_id: str | None = None
    lines: list[JournalLineInput] = Field(default_factory=list)
    idempotency_key: str | None = None


class JournalUpdateRequest(BaseModel):
    posting_date: str | None = None
    description: str | None = None
    journal_type: str | None = None
    lines: list[JournalLineInput] | None = None


class JournalApproveRequest(BaseModel):
    comment: str | None = None


class JournalReverseRequest(BaseModel):
    reversal_reason: str | None = None


class RecurringJournalCreateRequest(BaseModel):
    template_name: str = Field(min_length=2, max_length=128)
    frequency: str = Field(min_length=4, max_length=32)
    next_run_date: str = Field(min_length=10, max_length=10)
    journal_template: dict = Field(default_factory=dict)
    company_id: str | None = None


class AccrualCreateRequest(BaseModel):
    accrual_type: str = Field(min_length=2, max_length=64)
    accrual_date: str = Field(min_length=10, max_length=10)
    amount: float | None = Field(default=None, gt=0)
    estimated_expense: float | None = Field(default=None, ge=0)
    paid_amount: float = Field(default=0, ge=0)
    expense_account_id: str
    liability_account_id: str
    source_reference: str | None = None
    reversal_date: str | None = None
    company_id: str | None = None


class BatchPostRequest(BaseModel):
    journal_ids: list[str] = Field(min_length=1, max_length=50)


class JournalMarkReviewedRequest(BaseModel):
    comment: str | None = None


class AiJournalFromDocumentRequest(BaseModel):
    document_id: str
    extracted_data: dict = Field(default_factory=dict)
    posting_date: str = Field(min_length=10, max_length=10)
    journal_type: str = Field(default="purchase", max_length=32)
