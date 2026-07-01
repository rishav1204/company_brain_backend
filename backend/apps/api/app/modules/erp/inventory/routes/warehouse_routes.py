from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.inventory.schemas.inventory_schema import WarehouseCreateRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_create, require_inventory_read
from app.modules.erp.inventory.services.item_service import warehouse_service

router = APIRouter()


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
def create_warehouse(request: WarehouseCreateRequest, context=Depends(require_inventory_create)) -> dict:
    try:
        wh = warehouse_service.create(
            context.org_id,
            warehouse_code=request.warehouse_code,
            warehouse_name=request.warehouse_name,
            location=request.location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "warehouse": wh}


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
def list_warehouses(context=Depends(require_inventory_read)) -> dict:
    items = warehouse_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/{warehouse_id}")
def get_warehouse(warehouse_id: str, context=Depends(require_inventory_read)) -> dict:
    wh = warehouse_service.get(context.org_id, warehouse_id=warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return {"request_id": context.request_id, "warehouse": wh}
