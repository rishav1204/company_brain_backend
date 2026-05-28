from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.gl.schemas.fiscal_schema import FiscalPeriodCreateRequest
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.fiscal_period_service import fiscal_period_service

router = APIRouter()


@router.post("/fiscal-periods")
def create_period(
    request: FiscalPeriodCreateRequest, context=Depends(require_finance_gl_admin)
) -> dict:
    item = fiscal_period_service.create(
        context.org_id,
        period_name=request.period_name,
        start_date=request.start_date,
        end_date=request.end_date,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/fiscal-periods")
def list_periods(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = fiscal_period_service.list(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/fiscal-periods/{fiscal_period_id}/lock")
def lock_period(fiscal_period_id: str, context=Depends(require_finance_gl_admin)) -> dict:
    item = fiscal_period_service.lock(context.org_id, fiscal_period_id=fiscal_period_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/fiscal-periods/{fiscal_period_id}/close")
def close_period(fiscal_period_id: str, context=Depends(require_finance_gl_admin)) -> dict:
    item = fiscal_period_service.close(context.org_id, fiscal_period_id=fiscal_period_id)
    return {"request_id": context.request_id, "item": item}

