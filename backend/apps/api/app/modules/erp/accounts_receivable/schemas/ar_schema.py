from __future__ import annotations

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    customer_name: str = Field(min_length=2, max_length=256)
    customer_code: str | None = None
    customer_type: str = "corporate"
    gstin: str | None = None
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    credit_limit: float = Field(default=0, ge=0)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    receivable_account_id: str | None = None
    revenue_account_id: str | None = None
    company_id: str | None = None


class CustomerUpdateRequest(BaseModel):
    customer_name: str | None = None
    email: str | None = None
    phone: str | None = None
    credit_limit: float | None = Field(default=None, ge=0)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)


class CustomerAddressRequest(BaseModel):
    address_type: str = "billing"
    line1: str = Field(min_length=2)
    line2: str | None = None
    city: str | None = None
    state_code: str | None = None
    postal_code: str | None = None
    place_of_supply: str | None = None
    is_primary: bool = False


class InvoiceLineInput(BaseModel):
    account_id: str | None = None
    line_type: str = "revenue"
    description: str | None = None
    amount: float = Field(ge=0)
    tax_code: str | None = None
    cost_center_id: str | None = None


class SalesInvoiceCreateRequest(BaseModel):
    customer_id: str
    invoice_number: str = Field(min_length=1, max_length=64)
    invoice_date: str = Field(min_length=10, max_length=10)
    due_date: str | None = None
    subtotal: float = Field(ge=0)
    gst_amount: float = Field(ge=0)
    total_amount: float = Field(gt=0)
    cgst: float = Field(default=0, ge=0)
    sgst: float = Field(default=0, ge=0)
    igst: float = Field(default=0, ge=0)
    gst_rate: float | None = Field(default=None, ge=0, le=1)
    export_zero_rated: bool = False
    company_id: str | None = None
    contract_months: int | None = Field(default=None, ge=1)
    lines: list[InvoiceLineInput] = Field(default_factory=list)


class SalesInvoiceIssueRequest(BaseModel):
    auto_post: bool = True
    force_credit_approval: bool = False


class WriteOffRequest(BaseModel):
    bad_debt_account_id: str
    auto_post: bool = True


class ReceiptRecordRequest(BaseModel):
    customer_id: str
    receipt_date: str = Field(min_length=10, max_length=10)
    amount: float = Field(gt=0)
    payment_mode: str = "bank_transfer"
    bank_account_id: str
    company_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    invoice_allocations: list[dict] = Field(default_factory=list)


class ReceiptCompleteRequest(BaseModel):
    auto_post: bool = True


class CreditCheckRequest(BaseModel):
    customer_id: str
    invoice_amount: float = Field(gt=0)


class StatementRequest(BaseModel):
    opening_balance: float = 0
