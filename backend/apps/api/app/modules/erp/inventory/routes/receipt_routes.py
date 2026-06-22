from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.inventory.schemas.inventory_schema import GrnReceiptRequest, ReceiptRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_receive
from app.modules.erp.inventory.services.receipt_service import receipt_service

router = APIRouter()


@router.post("/")
def create_receipt(request: ReceiptRequest, context=Depends(require_inventory_receive)) -> dict:
    try:
        movement = receipt_service.receive_manual(
            context.org_id,
            item_id=request.item_id,
            warehouse_id=request.warehouse_id,
            quantity=request.quantity,
            unit_cost=request.unit_cost,
            movement_date=request.movement_date,
            actor_id=context.user_id,
            post_journal=request.post_journal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "movement": movement}


@router.post("/from-grn")
def receive_from_grn(request: GrnReceiptRequest, context=Depends(require_inventory_receive)) -> dict:
    try:
        movements = receipt_service.receive_from_grn(context.org_id, grn_id=request.grn_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "movements": movements}
