from __future__ import annotations

from pydantic import BaseModel, Field


class ClaimItemInput(BaseModel):
    expense_date: str | None = None
    expense_type: str = "miscellaneous"
    amount: float = Field(gt=0)
    merchant_name: str | None = None
    description: str | None = None
    gst_amount: float = Field(default=0, ge=0)
    receipt_id: str | None = None
    expense_account_id: str | None = None


class ClaimCreateRequest(BaseModel):
    employee_id: str | None = None
    claim_date: str | None = None
    expense_category: str | None = None
    company_id: str | None = None
    cost_center_id: str | None = None
    department_id: str | None = None
    items: list[ClaimItemInput] = Field(default_factory=list)


class ClaimRejectRequest(BaseModel):
    reason: str = Field(min_length=3)


class ClaimApproveRequest(BaseModel):
    auto_reimburse: bool = False


class ReceiptFromDocumentRequest(BaseModel):
    document_id: str
    employee_id: str | None = None
    extracted_data: dict | None = None
    company_id: str | None = None


class ReimbursementScheduleRequest(BaseModel):
    bank_account_id: str | None = None


class PolicyCreateRequest(BaseModel):
    policy_name: str = "default"
    expense_type: str
    max_amount: float | None = None
    max_per_day: float | None = None
    per_diem_rate: float | None = None
    requires_receipt: bool = True
    receipt_mandatory_above: float | None = 500
    requires_manager_approval: bool = True


class AdvanceIssueRequest(BaseModel):
    employee_id: str
    advance_amount: float = Field(gt=0)
    issued_date: str | None = None
    settlement_due_date: str | None = None


class CardAllocateRequest(BaseModel):
    claim_item_id: str


class CardImportRequest(BaseModel):
    employee_id: str | None = None
    transaction_date: str
    amount: float = Field(gt=0)
    merchant_name: str | None = None
    card_last4: str | None = None
    bank_feed_ref: str | None = None
