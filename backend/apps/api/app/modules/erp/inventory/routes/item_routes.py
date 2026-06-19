from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.inventory.schemas.inventory_schema import ItemCreateRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_create, require_inventory_read
from app.modules.erp.inventory.services.item_service import item_service

router = APIRouter()


@router.post("")
def create_item(request: ItemCreateRequest, context=Depends(require_inventory_create)) -> dict:
    try:
        item = item_service.create(
            context.org_id,
            item_name=request.item_name,
            item_code=request.item_code,
            item_type=request.item_type,
            uom=request.uom,
            valuation_method=request.valuation_method,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("")
def list_items(context=Depends(require_inventory_read), status: str | None = Query(default=None)) -> dict:
    items = item_service.list(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/{item_id}")
def get_item(item_id: str, context=Depends(require_inventory_read)) -> dict:
    item = item_service.get(context.org_id, item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"request_id": context.request_id, "item": item}
