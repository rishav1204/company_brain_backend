from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.accounts_receivable.schemas.ar_schema import StatementRequest
from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_read
from app.modules.erp.accounts_receivable.services.statement_service import statement_service

router = APIRouter()


@router.post("/statements/{customer_id}")
def customer_statement(
    customer_id: str,
    request: StatementRequest,
    context=Depends(require_ar_read),
) -> dict:
    try:
        item = statement_service.generate(
            context.org_id, customer_id=customer_id, opening_balance=request.opening_balance
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
