from __future__ import annotations

from pydantic import BaseModel, Field


class PrItemInput(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    expense_account_id: str | None = None


class PrCreateRequest(BaseModel):
    requester_id: str | None = None
    department_id: str | None = None
    cost_center_id: str | None = None
    required_date: str | None = None
    description: str | None = None
    company_id: str | None = None
    items: list[PrItemInput] = Field(default_factory=list)


class PrConvertPoRequest(BaseModel):
    vendor_id: str
    gst_amount: float = Field(default=0, ge=0)


class PoItemInput(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    hsn_sac: str | None = None


class PoCreateRequest(BaseModel):
    vendor_id: str
    pr_id: str | None = None
    po_date: str | None = None
    expected_delivery_date: str | None = None
    company_id: str | None = None
    gst_amount: float = Field(default=0, ge=0)
    items: list[PoItemInput] = Field(default_factory=list)


class GrnItemInput(BaseModel):
    po_item_id: str
    received_quantity: float = Field(gt=0)
    accepted_quantity: float | None = None
    rejected_quantity: float = Field(default=0, ge=0)


class GrnCreateRequest(BaseModel):
    po_id: str
    received_date: str | None = None
    items: list[GrnItemInput] = Field(min_length=1)


class MatchRunRequest(BaseModel):
    po_id: str
    grn_id: str | None = None
    ap_invoice_id: str | None = None


class MatchOverrideRequest(BaseModel):
    reason: str = Field(min_length=5)


class VendorRecommendRequest(BaseModel):
    item_hint: str = ""
    limit: int = Field(default=5, ge=1, le=20)
