from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.accounts_receivable.schemas.ar_schema import CreditCheckRequest
from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_read
from app.modules.erp.accounts_receivable.services.credit_limit_service import credit_limit_service

router = APIRouter()


@router.post("/credit/check")
def credit_check(request: CreditCheckRequest, context=Depends(require_ar_read)) -> dict:
    try:
        item = credit_limit_service.check_before_issue(
            context.org_id, customer_id=request.customer_id, invoice_amount=request.invoice_amount
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
