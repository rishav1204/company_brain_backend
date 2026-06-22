from __future__ import annotations

from pydantic import BaseModel, Field


class VoucherLineInput(BaseModel):
    account_id: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    narration: str | None = None
    cost_center_id: str | None = None
    tax_code: str | None = None
    party_type: str | None = None
    party_id: str | None = None


class VoucherCreateRequest(BaseModel):
    voucher_type: str = Field(min_length=1, max_length=50)
    voucher_date: str = Field(min_length=10, max_length=10)
    narration: str | None = None
    company_id: str | None = None
    branch_id: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    lines: list[VoucherLineInput] = Field(default_factory=list)
    idempotency_key: str | None = None
    metadata: dict | None = None


class VoucherApproveRequest(BaseModel):
    auto_post: bool = False


class PurchaseVoucherCreateRequest(BaseModel):
    voucher_date: str
    vendor_id: str | None = None
    expense_account_id: str
    payable_account_id: str
    invoice_amount: float
    gst_amount: float = 0.0
    total_amount: float
    narration: str | None = None
    company_id: str | None = None
    gst_lines: list[dict] | None = None


class SalesVoucherCreateRequest(BaseModel):
    voucher_date: str
    receivable_account_id: str
    revenue_account_id: str
    subtotal: float
    gst_amount: float = 0.0
    total_amount: float
    narration: str | None = None
    company_id: str | None = None
    gst_lines: list[dict] | None = None


class PaymentVoucherCreateRequest(BaseModel):
    voucher_date: str
    payable_account_id: str
    bank_account_id: str
    amount: float
    narration: str | None = None
    company_id: str | None = None


class ReceiptVoucherCreateRequest(BaseModel):
    voucher_date: str
    bank_account_id: str
    receivable_account_id: str
    amount: float
    narration: str | None = None
    company_id: str | None = None


class ContraVoucherCreateRequest(BaseModel):
    voucher_date: str
    from_account_id: str
    to_account_id: str
    amount: float
    narration: str | None = None
    company_id: str | None = None


class JournalVoucherCreateRequest(BaseModel):
    voucher_date: str
    narration: str | None = None
    company_id: str | None = None
    lines: list[VoucherLineInput] = Field(min_length=2)


class CreditDebitNoteCreateRequest(BaseModel):
    voucher_date: str
    reference_invoice_id: str
    amount: float
    gst_amount: float = 0.0
    total_amount: float
    narration: str | None = None
    company_id: str | None = None
    expense_account_id: str | None = None
    revenue_account_id: str | None = None
