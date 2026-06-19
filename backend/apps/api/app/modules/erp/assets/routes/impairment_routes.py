from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.assets.schemas.asset_schema import ImpairmentRequest
from app.modules.erp.assets.security.asset_guard import require_asset_impair
from app.modules.erp.assets.services.impairment_service import impairment_service

router = APIRouter()


@router.post("/{asset_id}/impair")
def impair_asset(asset_id: str, request: ImpairmentRequest, context=Depends(require_asset_impair)) -> dict:
    try:
        item = impairment_service.impair(
            context.org_id,
            asset_id=asset_id,
            impairment_amount=request.impairment_amount,
            impairment_date=request.impairment_date,
            reason=request.reason,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
