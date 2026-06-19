from __future__ import annotations

from pydantic import BaseModel, Field


class AssetCreateRequest(BaseModel):
    asset_name: str = Field(min_length=1, max_length=255)
    asset_category_id: str | None = None
    purchase_date: str | None = None
    cost: float = Field(gt=0)
    salvage_value: float | None = Field(default=None, ge=0)
    useful_life_months: int | None = Field(default=None, gt=0)
    company_id: str | None = None
    location: str | None = None
    department_id: str | None = None
    custodian_id: str | None = None
    cost_center_id: str | None = None


class AssetCapitalizeRequest(BaseModel):
    reclass_from_expense: bool = False
    credit_account_id: str | None = None
    auto_post: bool = True


class DepreciationRunRequest(BaseModel):
    as_of_date: str | None = None


class TransferRequest(BaseModel):
    to_department_id: str | None = None
    to_location: str | None = None
    to_custodian_id: str | None = None
    transfer_date: str | None = None
    reason: str | None = None


class DisposalRequest(BaseModel):
    sale_amount: float = Field(ge=0)
    disposal_date: str | None = None
    bank_account_id: str | None = None
    reason: str | None = None


class ImpairmentRequest(BaseModel):
    impairment_amount: float = Field(gt=0)
    impairment_date: str | None = None
    reason: str | None = None


class CandidateConvertRequest(BaseModel):
    asset_name: str | None = None


class CopilotSuggestRequest(BaseModel):
    description: str
    amount: float = Field(gt=0)
