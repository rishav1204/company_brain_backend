from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.accounts_payable.schemas.ap_schema import StatementReconcileRequest
from app.modules.erp.accounts_payable.security.ap_guard import require_ap_read
from app.modules.erp.accounts_payable.services.statement_service import statement_service

router = APIRouter()


@router.post("/statements/{vendor_id}/reconcile")
def reconcile_statement(
    vendor_id: str,
    request: StatementReconcileRequest,
    context=Depends(require_ap_read),
) -> dict:
    try:
        item = statement_service.reconcile(
            context.org_id,
            vendor_id=vendor_id,
            statement_lines=request.statement_lines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
