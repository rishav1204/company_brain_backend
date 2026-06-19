from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.assets.schemas.asset_schema import DisposalRequest
from app.modules.erp.assets.security.asset_guard import require_asset_dispose
from app.modules.erp.assets.services.disposal_service import disposal_service

router = APIRouter()


@router.post("/{asset_id}/dispose")
def dispose_asset(asset_id: str, request: DisposalRequest, context=Depends(require_asset_dispose)) -> dict:
    try:
        item = disposal_service.dispose(
            context.org_id,
            asset_id=asset_id,
            sale_amount=request.sale_amount,
            disposal_date=request.disposal_date,
            bank_account_id=request.bank_account_id,
            reason=request.reason,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
