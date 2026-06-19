from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.fiscal.schemas.fiscal_schema import FiscalYearCreateRequest
from app.modules.erp.fiscal.security.fiscal_guard import require_fiscal_admin, require_fiscal_read
from app.modules.erp.fiscal.services.fiscal_year_service import fiscal_year_service

router = APIRouter()


@router.get("/fiscal-years")
def list_fiscal_years(context=Depends(require_fiscal_read), company_id: str | None = Query(default=None)) -> dict:
    items = fiscal_year_service.list_fiscal_years(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/fiscal-years")
def create_fiscal_year(request: FiscalYearCreateRequest, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = fiscal_year_service.create_fiscal_year(
            context.org_id,
            start_date=request.start_date,
            end_date=request.end_date,
            fiscal_year_code=request.fiscal_year_code,
            company_id=request.company_id,
            set_current=request.set_current,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
