from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.fiscal.schemas.fiscal_schema import FiscalPeriodCreateRequest
from app.modules.erp.fiscal.security.fiscal_guard import require_fiscal_admin, require_fiscal_read
from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service

router = APIRouter()


@router.get("/periods")
def list_periods(
    context=Depends(require_fiscal_read),
    fiscal_year_id: str | None = Query(default=None),
    company_id: str | None = Query(default=None),
) -> dict:
    items = fiscal_period_service.list(context.org_id, fiscal_year_id=fiscal_year_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/periods")
def create_period(request: FiscalPeriodCreateRequest, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = fiscal_period_service.create(
            context.org_id,
            period_name=request.period_name,
            start_date=request.start_date,
            end_date=request.end_date,
            fiscal_year_id=request.fiscal_year_id,
            period_number=request.period_number,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/periods/{period_id}")
def get_period(period_id: str, context=Depends(require_fiscal_read)) -> dict:
    try:
        item = fiscal_period_service.get(context.org_id, period_id=period_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
