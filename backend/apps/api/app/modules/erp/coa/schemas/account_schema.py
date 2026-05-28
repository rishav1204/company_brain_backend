from __future__ import annotations

from pydantic import BaseModel, Field


class AccountGroupCreateRequest(BaseModel):
    group_name: str = Field(min_length=2, max_length=256)
    group_code: str = Field(min_length=1, max_length=64)
    parent_group_id: str | None = None
    group_type: str = Field(min_length=3, max_length=32)
    nature: str = Field(min_length=4, max_length=16)
    company_id: str | None = None


class AccountGroupUpdateRequest(BaseModel):
    group_name: str = Field(min_length=2, max_length=256)
    parent_group_id: str | None = None


class AccountCreateRequest(BaseModel):
    account_code: str = Field(min_length=1, max_length=64)
    account_name: str = Field(min_length=2, max_length=256)
    account_type: str = Field(min_length=3, max_length=32)
    group_id: str
    parent_account_id: str | None = None
    is_postable: bool = True
    currency_code: str = Field(default="INR", max_length=8)
    company_id: str | None = None


class AccountUpdateRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=256)
    parent_account_id: str | None = None


class CostCenterCreateRequest(BaseModel):
    cost_center_code: str = Field(min_length=1, max_length=64)
    cost_center_name: str = Field(min_length=2, max_length=256)
    parent_cost_center_id: str | None = None
    company_id: str | None = None


class CostCenterUpdateRequest(BaseModel):
    cost_center_name: str = Field(min_length=2, max_length=256)
    parent_cost_center_id: str | None = None


class FinancialMappingCreateRequest(BaseModel):
    account_id: str
    statement_type: str = Field(min_length=3, max_length=32)
    reporting_category: str = Field(min_length=2, max_length=128)
    company_id: str | None = None


class GstMappingCreateRequest(BaseModel):
    account_id: str
    gst_type: str = Field(min_length=3, max_length=32)
    itc_eligible: bool = False
    company_id: str | None = None

