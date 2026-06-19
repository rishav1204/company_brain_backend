from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.fiscal.schemas.fiscal_schema import YearEndRequest
from app.modules.erp.fiscal.security.fiscal_guard import require_fiscal_admin
from app.modules.erp.fiscal.services.year_end_service import year_end_service

router = APIRouter()


@router.post("/year-end")
def run_year_end(request: YearEndRequest, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = year_end_service.run_year_end(
            context.org_id,
            fiscal_year_id=request.fiscal_year_id,
            run_by=context.user_id,
            retained_earnings_account_id=request.retained_earnings_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
