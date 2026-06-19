from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.assets.repositories.category_repository import category_repository
from app.modules.erp.assets.schemas.asset_schema import AssetCapitalizeRequest, AssetCreateRequest
from app.modules.erp.assets.security.asset_guard import (
    require_asset_capitalize,
    require_asset_create,
    require_asset_read,
)
from app.modules.erp.assets.services.asset_service import asset_service
from app.modules.erp.assets.services.capitalization_service import capitalization_service

router = APIRouter()


@router.post("")
def create_asset(request: AssetCreateRequest, context=Depends(require_asset_create)) -> dict:
    try:
        item = asset_service.create(
            context.org_id,
            asset_name=request.asset_name,
            asset_category_id=request.asset_category_id,
            purchase_date=request.purchase_date,
            cost=request.cost,
            salvage_value=request.salvage_value,
            useful_life_months=request.useful_life_months,
            company_id=request.company_id,
            location=request.location,
            department_id=request.department_id,
            custodian_id=request.custodian_id,
            cost_center_id=request.cost_center_id,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("")
def list_assets(
    context=Depends(require_asset_read),
    status: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
) -> dict:
    items = asset_service.list(context.org_id, status=status, category_id=category_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/categories/list")
def list_categories(context=Depends(require_asset_read)) -> dict:
    items = category_repository.list_active(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/{asset_id}")
def get_asset(asset_id: str, context=Depends(require_asset_read)) -> dict:
    item = asset_service.get(context.org_id, asset_id=asset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/{asset_id}/submit")
def submit_asset(asset_id: str, context=Depends(require_asset_create)) -> dict:
    try:
        item = asset_service.submit(context.org_id, asset_id=asset_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/{asset_id}/capitalize")
def capitalize_asset(
    asset_id: str,
    request: AssetCapitalizeRequest,
    context=Depends(require_asset_capitalize),
) -> dict:
    try:
        item = capitalization_service.capitalize(
            context.org_id,
            asset_id=asset_id,
            approver_id=context.user_id,
            reclass_from_expense=request.reclass_from_expense,
            credit_account_id=request.credit_account_id,
            auto_post=request.auto_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
