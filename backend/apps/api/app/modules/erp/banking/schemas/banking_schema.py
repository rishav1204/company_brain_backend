from __future__ import annotations

from pydantic import BaseModel, Field


class BankAccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=256)
    bank_name: str = Field(min_length=2, max_length=128)
    account_number: str = Field(min_length=4, max_length=32)
    ifsc_code: str = Field(min_length=11, max_length=11)
    currency_code: str = "INR"
    account_type: str = "current"
    ledger_account_id: str
    company_id: str | None = None
    opening_balance: float = 0


class BankAccountUpdateRequest(BaseModel):
    account_name: str | None = None
    is_active: bool | None = None
    ledger_account_id: str | None = None


class BankTransactionImportRequest(BaseModel):
    bank_account_id: str
    provider: str = "stub_bank"
    transactions: list[dict] = Field(default_factory=list)


class BankFeedSyncRequest(BaseModel):
    bank_account_id: str
    provider: str = "stub_bank"
    payload: dict = Field(default_factory=dict)


class PaymentRequestCreate(BaseModel):
    payment_type: str
    beneficiary_type: str
    beneficiary_ref: str | None = None
    bank_account_id: str
    amount: float = Field(gt=0)
    currency_code: str = "INR"
    scheduled_date: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    company_id: str | None = None
    expense_account_id: str | None = None
    dest_bank_account_id: str | None = None
    vendor_bank_account_id: str | None = None
    ap_payment_id: str | None = None
    beneficiary_id: str | None = None


class PaymentExecuteRequest(BaseModel):
    auto_post: bool = True


class BeneficiaryCreateRequest(BaseModel):
    beneficiary_name: str
    account_number: str
    ifsc_code: str
    bank_name: str | None = None
    vendor_id: str | None = None
    customer_id: str | None = None


class ReceiptCreateRequest(BaseModel):
    customer_id: str
    bank_account_id: str
    amount: float = Field(gt=0)
    receipt_date: str
    payment_mode: str = "bank_transfer"
    reference: str | None = None


class BankingCopilotRequest(BaseModel):
    question: str = Field(min_length=3, max_length=512)
