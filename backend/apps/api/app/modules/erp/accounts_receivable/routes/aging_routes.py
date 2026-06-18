from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_read
from app.modules.erp.accounts_receivable.services.aging_service import aging_service
from app.modules.erp.accounts_receivable.services.customer_balance_service import customer_balance_service

router = APIRouter()


@router.get("/aging")
def aging_report(
    context=Depends(require_ar_read),
    as_of: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
) -> dict:
    item = aging_service.report(context.org_id, as_of=as_of, customer_id=customer_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/aging/customer-balances")
def customer_balances(context=Depends(require_ar_read)) -> dict:
    items = customer_balance_service.list_balances(context.org_id)
    return {"request_id": context.request_id, "items": items}
