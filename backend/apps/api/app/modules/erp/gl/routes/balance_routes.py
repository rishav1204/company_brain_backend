from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.balance_service import balance_service

router = APIRouter()


@router.get("/gl/balances")
def list_balances(
    fiscal_period_id: str = Query(...),
    context=Depends(build_request_context),
) -> dict:
    items = balance_service.list_by_period(context.org_id, fiscal_period_id=fiscal_period_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/gl/balances/{fiscal_period_id}/recompute")
def recompute_balances(fiscal_period_id: str, context=Depends(require_finance_gl_admin)) -> dict:
    item = balance_service.recompute_period(context.org_id, fiscal_period_id=fiscal_period_id)
    return {"request_id": context.request_id, "item": item}

