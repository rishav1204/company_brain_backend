from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.inventory.schemas.inventory_schema import AdjustmentRequest, TransferRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_adjust, require_inventory_transfer
from app.modules.erp.inventory.services.adjustment_service import adjustment_service
from app.modules.erp.inventory.services.movement_service import movement_service

router = APIRouter()


@router.post("/transfers")
def transfer_stock(request: TransferRequest, context=Depends(require_inventory_transfer)) -> dict:
    try:
        result = movement_service.transfer(
            context.org_id,
            item_id=request.item_id,
            from_warehouse_id=request.from_warehouse_id,
            to_warehouse_id=request.to_warehouse_id,
            quantity=request.quantity,
            movement_date=request.movement_date,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, **result}


@router.post("/adjustments")
def create_adjustment(request: AdjustmentRequest, context=Depends(require_inventory_adjust)) -> dict:
    try:
        result = adjustment_service.create(
            context.org_id,
            item_id=request.item_id,
            warehouse_id=request.warehouse_id,
            quantity_variance=request.quantity_variance,
            adjustment_date=request.adjustment_date,
            reason=request.reason,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, **result}
