from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.expenses.ai.spend_analyzer import analyze_spend
from app.modules.erp.expenses.security.expense_guard import require_expense_read
from app.modules.erp.expenses.services.card_expense_service import card_expense_service

router = APIRouter()


@router.get("/analytics/spend")
def spend_analytics(
    context=Depends(require_expense_read),
    employee_id: str | None = Query(default=None),
) -> dict:
    summary = analyze_spend(context.org_id, employee_id=employee_id)
    return {"request_id": context.request_id, "summary": summary}


@router.get("/card-transactions")
def list_card_transactions(
    context=Depends(require_expense_read),
    employee_id: str | None = Query(default=None),
) -> dict:
    items = card_expense_service.list_unallocated(context.org_id, employee_id=employee_id)
    return {"request_id": context.request_id, "items": items}
