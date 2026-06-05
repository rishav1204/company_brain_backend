from __future__ import annotations

from pydantic import BaseModel, Field


class VendorCreateRequest(BaseModel):
    vendor_name: str = Field(min_length=2, max_length=256)
    vendor_code: str | None = None
    gstin: str | None = None
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    payable_account_id: str | None = None
    company_id: str | None = None
    early_payment_discount_rate: float = Field(default=0, ge=0, le=1)
    early_payment_discount_days: int = Field(default=0, ge=0, le=90)


class VendorUpdateRequest(BaseModel):
    vendor_name: str | None = None
    email: str | None = None
    phone: str | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    payable_account_id: str | None = None
    early_payment_discount_rate: float | None = Field(default=None, ge=0, le=1)
    early_payment_discount_days: int | None = Field(default=None, ge=0, le=90)


class VendorBankAccountRequest(BaseModel):
    account_number: str = Field(min_length=4)
    ifsc_code: str = Field(min_length=11, max_length=11)
    bank_name: str | None = None
    is_primary: bool = False


class InvoiceLineInput(BaseModel):
    account_id: str | None = None
    line_type: str = "expense"
    description: str | None = None
    amount: float = Field(ge=0)
    tax_code: str | None = None
    cost_center_id: str | None = None


class InvoiceCreateRequest(BaseModel):
    vendor_id: str
    invoice_number: str = Field(min_length=1, max_length=64)
    invoice_date: str = Field(min_length=10, max_length=10)
    due_date: str | None = None
    invoice_amount: float = Field(ge=0)
    gst_amount: float = Field(ge=0)
    total_amount: float = Field(gt=0)
    source_document_id: str | None = None
    company_id: str | None = None
    expense_account_id: str | None = None
    lines: list[InvoiceLineInput] = Field(default_factory=list)


class InvoiceUpdateRequest(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    invoice_amount: float | None = Field(default=None, ge=0)
    gst_amount: float | None = Field(default=None, ge=0)
    total_amount: float | None = Field(default=None, gt=0)
    expense_account_id: str | None = None
    lines: list[InvoiceLineInput] = Field(default_factory=list)


class InvoiceApproveRequest(BaseModel):
    expense_account_id: str | None = None
    auto_post: bool = False


class AiInvoiceFromDocumentRequest(BaseModel):
    document_id: str | None = None
    extracted_data: dict = Field(default_factory=dict)
    company_id: str | None = None


class PaymentScheduleRequest(BaseModel):
    vendor_id: str
    payment_date: str = Field(min_length=10, max_length=10)
    amount: float = Field(gt=0)
    bank_account_id: str
    company_id: str | None = None
    invoice_allocations: list[dict] = Field(default_factory=list)


class PaymentExecuteRequest(BaseModel):
    payable_account_id: str | None = None


class StatementReconcileRequest(BaseModel):
    statement_lines: list[dict] = Field(default_factory=list)


class PaymentScheduleProposalRequest(BaseModel):
    cash_available: float = Field(gt=0)
    as_of_date: str | None = None


class PaymentRecommendationsRequest(BaseModel):
    cash_available: float = Field(gt=0)
    as_of_date: str | None = None
