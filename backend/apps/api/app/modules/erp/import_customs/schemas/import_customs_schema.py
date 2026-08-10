from __future__ import annotations

from pydantic import BaseModel, Field


class BillOfEntryCreateRequest(BaseModel):
    boe_number: str = Field(..., min_length=1, max_length=64)
    boe_date: str
    assessable_value: float = Field(..., ge=0)
    customs_duty: float = Field(default=0, ge=0)
    igst_import: float = Field(default=0, ge=0)
    company_id: str | None = None
    branch_id: str | None = None
    port_code: str | None = None
    vendor_id: str | None = None
    po_id: str | None = None
    currency_code: str = "INR"
    exchange_rate: float = Field(default=1.0, gt=0)
