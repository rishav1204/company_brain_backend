from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.erp.journals.schemas.journal_schema import AccrualCreateRequest
from app.modules.erp.journals.security.journal_guard import require_finance_journal_admin
from app.modules.erp.journals.services.accrual_service import accrual_service

router = APIRouter()


@router.post("/accruals")
def create_accrual(request: AccrualCreateRequest, context=Depends(require_finance_journal_admin)) -> dict:
    try:
        item = accrual_service.create_accrual(
            context.org_id,
            accrual_type=request.accrual_type,
            accrual_date=request.accrual_date,
            amount=request.amount,
            estimated_expense=request.estimated_expense,
            paid_amount=request.paid_amount,
            expense_account_id=request.expense_account_id,
            liability_account_id=request.liability_account_id,
            source_reference=request.source_reference,
            reversal_date=request.reversal_date,
            company_id=request.company_id,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/accruals")
def list_accruals(context=Depends(build_request_context)) -> dict:
    items = accrual_service.list_accruals(context.org_id)
    return {"request_id": context.request_id, "items": items}
