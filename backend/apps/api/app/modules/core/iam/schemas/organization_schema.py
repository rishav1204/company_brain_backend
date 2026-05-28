from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    country_code: str
    timezone: str
    currency: str
    plan: str


class CompanyResponse(BaseModel):
    id: str
    org_id: str
    legal_name: str
    gstin: str | None = None
    pan: str | None = None
    base_currency: str
    financial_year_start: str


class BranchResponse(BaseModel):
    id: str
    company_id: str
    org_id: str
    branch_code: str
    branch_name: str
    state_code: str | None = None
    address: dict = Field(default_factory=dict)
