from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.assets.schemas.asset_schema import TransferRequest
from app.modules.erp.assets.security.asset_guard import require_asset_transfer
from app.modules.erp.assets.services.transfer_service import transfer_service

router = APIRouter()


@router.post("/{asset_id}/transfer")
def transfer_asset(asset_id: str, request: TransferRequest, context=Depends(require_asset_transfer)) -> dict:
    try:
        item = transfer_service.transfer(
            context.org_id,
            asset_id=asset_id,
            to_department_id=request.to_department_id,
            to_location=request.to_location,
            to_custodian_id=request.to_custodian_id,
            transfer_date=request.transfer_date,
            reason=request.reason,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
