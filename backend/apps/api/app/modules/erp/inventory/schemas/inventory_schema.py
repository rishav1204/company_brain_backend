from __future__ import annotations

from pydantic import BaseModel, Field


class ItemCreateRequest(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    item_code: str | None = None
    item_type: str = "trading_goods"
    uom: str = "EA"
    valuation_method: str | None = None
    company_id: str | None = None


class WarehouseCreateRequest(BaseModel):
    warehouse_code: str = Field(min_length=1, max_length=50)
    warehouse_name: str = Field(min_length=1, max_length=255)
    location: str | None = None


class ReceiptRequest(BaseModel):
    item_id: str
    warehouse_id: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    movement_date: str | None = None
    post_journal: bool = True


class GrnReceiptRequest(BaseModel):
    grn_id: str


class IssueRequest(BaseModel):
    item_id: str
    warehouse_id: str
    quantity: float = Field(gt=0)
    movement_type: str = "issue"
    movement_date: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    post_journal: bool = True


class TransferRequest(BaseModel):
    item_id: str
    from_warehouse_id: str
    to_warehouse_id: str
    quantity: float = Field(gt=0)
    movement_date: str | None = None


class AdjustmentRequest(BaseModel):
    item_id: str
    warehouse_id: str
    quantity_variance: float
    adjustment_date: str | None = None
    reason: str | None = None


class ValuationRunRequest(BaseModel):
    valuation_date: str | None = None


class InventoryAnalyzeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
