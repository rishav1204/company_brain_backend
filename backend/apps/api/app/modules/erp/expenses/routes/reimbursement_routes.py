from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.expenses.schemas.expense_schema import ReimbursementScheduleRequest
from app.modules.erp.expenses.security.expense_guard import require_expense_reimburse
from app.modules.erp.expenses.services.reimbursement_service import reimbursement_service

router = APIRouter()


@router.post("/claims/{claim_id}/reimburse")
def schedule_reimbursement(
    claim_id: str,
    request: ReimbursementScheduleRequest,
    context=Depends(require_expense_reimburse),
) -> dict:
    try:
        item = reimbursement_service.schedule(
            context.org_id,
            claim_id=claim_id,
            actor_id=context.user_id,
            bank_account_id=request.bank_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/reimbursements/{payment_request_id}/execute")
def execute_reimbursement(payment_request_id: str, context=Depends(require_expense_reimburse)) -> dict:
    try:
        item = reimbursement_service.execute(
            context.org_id, payment_request_id=payment_request_id, actor_id=context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
