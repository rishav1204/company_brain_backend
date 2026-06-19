from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.assets.schemas.asset_schema import DepreciationRunRequest
from app.modules.erp.assets.security.asset_guard import require_asset_depreciate, require_asset_read
from app.modules.erp.assets.services.asset_register_service import asset_register_service
from app.modules.erp.assets.services.depreciation_service import depreciation_service

router = APIRouter()


@router.post("/depreciate")
def run_depreciation(request: DepreciationRunRequest, context=Depends(require_asset_depreciate)) -> dict:
    try:
        items = depreciation_service.run_due(context.org_id, as_of_date=request.as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "items": items}


@router.post("/{asset_id}/depreciate")
def depreciate_asset(asset_id: str, context=Depends(require_asset_depreciate)) -> dict:
    try:
        item = depreciation_service.depreciate_asset(context.org_id, asset_id=asset_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/{asset_id}/depreciation")
def depreciation_history(asset_id: str, context=Depends(require_asset_read)) -> dict:
    items = asset_register_service.depreciation_history(context.org_id, asset_id=asset_id)
    return {"request_id": context.request_id, "items": items}
