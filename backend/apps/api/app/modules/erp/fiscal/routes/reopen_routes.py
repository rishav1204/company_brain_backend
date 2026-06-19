from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation
from app.modules.erp.fiscal.schemas.fiscal_schema import ReopenRequest
from app.modules.erp.fiscal.security.fiscal_guard import require_fiscal_admin
from app.modules.erp.fiscal.services.reopen_service import reopen_service

router = APIRouter()


@router.post("/periods/{period_id}/reopen")
def request_reopen(period_id: str, request: ReopenRequest, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = reopen_service.request_reopen(
            context.org_id,
            period_id=period_id,
            reason=request.reason,
            requested_by=context.user_id,
        )
    except MakerCheckerViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
