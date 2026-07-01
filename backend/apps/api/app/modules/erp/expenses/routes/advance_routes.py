from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.expenses.schemas.expense_schema import AdvanceIssueRequest
from app.modules.erp.expenses.security.expense_guard import require_expense_approve, require_expense_read
from app.modules.erp.expenses.services.advance_service import advance_service

router = APIRouter()


@router.post("/advances")
def issue_advance(request: AdvanceIssueRequest, context=Depends(require_expense_approve)) -> dict:
    try:
        item = advance_service.issue(
            context.org_id,
            employee_id=request.employee_id,
            advance_amount=request.advance_amount,
            issued_date=request.issued_date,
            settlement_due_date=request.settlement_due_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/advances")
def list_advances(
    context=Depends(require_expense_read),
    employee_id: str | None = Query(default=None),
) -> dict:
    items = advance_service.list_open(context.org_id, employee_id=employee_id)
    return {"request_id": context.request_id, "items": items}
