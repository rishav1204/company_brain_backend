from __future__ import annotations

from pydantic import BaseModel, Field


class GstRegistrationCreate(BaseModel):
    gstin: str
    legal_name: str
    trade_name: str | None = None
    state_code: str = Field(min_length=2, max_length=2)
    registration_type: str = "regular"


class GstReturnGenerateRequest(BaseModel):
    return_type: str = Field(pattern="^(GSTR-1|GSTR-3B|GSTR-9)$")
    return_period: str = Field(pattern=r"^(\d{4}-\d{2}|\d{4})$")


class GstCalculateRequest(BaseModel):
    taxable_value: float = Field(gt=0)
    gst_rate: float = Field(ge=0)
    supplier_state: str = Field(min_length=2, max_length=2)
    place_of_supply: str | None = Field(default=None, min_length=2, max_length=2)
    party_gstin: str | None = None
    gst_type: str = "sales"
    export_zero_rated: bool = False


class Gstr2bImportRequest(BaseModel):
    return_period: str
    rows: list[dict]


class ItcClaimRequest(BaseModel):
    claimed_amount: float


class TdsCalculateRequest(BaseModel):
    section_code: str
    gross_amount: float
    vendor_id: str | None = None
    prior_ytd: float = 0
    pan_present: bool = True


class TdsDeductRequest(BaseModel):
    payment_id: str
    section_code: str | None = None


class TdsChallanCreateRequest(BaseModel):
    amount: float
    deposit_date: str | None = None
    bsr_code: str | None = None
    cin: str | None = None
    challan_no: str | None = None
    quarter: str | None = None
    financial_year: str | None = None
    transaction_ids: list[str] | None = None
    tax_type: str = "TDS"


class TdsChallanPayRequest(BaseModel):
    challan_no: str | None = None
    bsr_code: str | None = None
    cin: str | None = None
    deposit_date: str | None = None


class Form16aGenerateRequest(BaseModel):
    vendor_id: str
    quarter: str = Field(pattern=r"^Q[1-4]$")
    financial_year: str


class Tds26asReconcileRequest(BaseModel):
    financial_year: str
    quarter: str | None = None
    rows: list[dict]


class TdsRecommendSectionRequest(BaseModel):
    payment_type: str | None = None
    expense_category: str | None = None
    vendor_id: str | None = None
    amount: float = 0


class TdsReviewRequest(BaseModel):
    vendor_id: str
    quarter: str = Field(pattern=r"^Q[1-4]$")
    financial_year: str


class TdsReturnReviewRequest(BaseModel):
    return_id: str


class TdsChallanValidateRequest(BaseModel):
    challan_no: str
    bsr_code: str | None = None
    amount: float


class EInvoiceGenerateRequest(BaseModel):
    force: bool = False


class EwayBillGenerateRequest(BaseModel):
    source_type: str = "ar_invoice"
    source_id: str
    distance_km: int | None = None


class TaxNoticeCreate(BaseModel):
    notice_type: str
    received_date: str
    document_id: str | None = None
    metadata: dict | None = None


class ComplianceCopilotRequest(BaseModel):
    question: str


class ItcBlockedRuleCreate(BaseModel):
    category: str
    description: str | None = None
    block_percentage: float = 100


class ItcBlockedRuleUpdate(BaseModel):
    description: str | None = None
    block_percentage: float | None = None
    is_active: bool | None = None


class TaxRateCreate(BaseModel):
    hsn_sac: str | None = None
    description: str | None = None
    gst_rate: float
    cess_rate: float = 0


class TdsReturnGenerateRequest(BaseModel):
    return_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    form_type: str = "26Q"


class EInvoiceCancelRequest(BaseModel):
    reason: str = ""


class EwayBillCancelRequest(BaseModel):
    reason: str = ""
