from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.payroll.schemas.payroll_schema import (
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    SalaryRunRequest,
)
from app.modules.erp.payroll.security.payroll_guard import require_payroll_admin, require_payroll_read
from app.modules.erp.payroll.services.salary_run_service import salary_run_service

router = APIRouter()


@router.post("/employees")
def create_employee(request: EmployeeCreateRequest, context=Depends(require_payroll_admin)) -> dict:
    try:
        item = salary_run_service.create_employee(
            context.org_id,
            employee_code=request.employee_code,
            pan=request.pan,
            name=request.name,
            date_of_joining=request.date_of_joining,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/employees")
def list_employees(
    context=Depends(require_payroll_read), status: str | None = Query(default="active")
) -> dict:
    items = salary_run_service.list_employees(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str, context=Depends(require_payroll_read)) -> dict:
    try:
        item = salary_run_service.get_employee(context.org_id, employee_id=employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/employees/{employee_id}")
def update_employee(
    employee_id: str, request: EmployeeUpdateRequest, context=Depends(require_payroll_admin)
) -> dict:
    try:
        item = salary_run_service.update_employee(
            context.org_id,
            employee_id=employee_id,
            name=request.name,
            pan=request.pan,
            date_of_joining=request.date_of_joining,
            status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/salary-runs")
def run_salary(request: SalaryRunRequest, context=Depends(require_payroll_admin)) -> dict:
    try:
        item = salary_run_service.run_salary(
            context.org_id,
            employee_id=request.employee_id,
            return_period=request.return_period,
            gross_salary=request.gross_salary,
            payment_date=request.payment_date,
            challan_number=request.challan_number,
            prior_ytd_gross=request.prior_ytd_gross,
            prior_ytd_tds=request.prior_ytd_tds,
            other_income_annual=request.other_income_annual,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/salary-runs")
def list_salary_runs(
    context=Depends(require_payroll_read),
    return_period: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
) -> dict:
    items = salary_run_service.list_salary_runs(
        context.org_id, return_period=return_period, employee_id=employee_id
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/salary-runs/{run_id}")
def get_salary_run(run_id: str, context=Depends(require_payroll_read)) -> dict:
    try:
        item = salary_run_service.get_salary_run(context.org_id, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
