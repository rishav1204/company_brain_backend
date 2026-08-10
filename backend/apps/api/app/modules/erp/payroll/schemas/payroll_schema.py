from __future__ import annotations

from pydantic import BaseModel, Field


class EmployeeCreateRequest(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=64)
    pan: str = Field(..., min_length=10, max_length=10)
    name: str = Field(..., min_length=1, max_length=256)
    date_of_joining: str | None = None
    company_id: str | None = None


class EmployeeUpdateRequest(BaseModel):
    name: str | None = None
    pan: str | None = Field(default=None, min_length=10, max_length=10)
    date_of_joining: str | None = None
    status: str | None = None


class SalaryRunRequest(BaseModel):
    employee_id: str
    return_period: str = Field(..., description="YYYY-MM deduction period")
    gross_salary: float = Field(..., gt=0)
    payment_date: str | None = None
    challan_number: str | None = None
    prior_ytd_gross: float | None = None
    prior_ytd_tds: float | None = None
    other_income_annual: float = 0.0
