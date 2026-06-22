from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.inventory.schemas.inventory_schema import IssueRequest
from app.modules.erp.inventory.security.inventory_guard import require_inventory_issue
from app.modules.erp.inventory.services.issue_service import issue_service

router = APIRouter()


@router.post("/")
def create_issue(request: IssueRequest, context=Depends(require_inventory_issue)) -> dict:
    try:
        movement = issue_service.issue(
            context.org_id,
            item_id=request.item_id,
            warehouse_id=request.warehouse_id,
            quantity=request.quantity,
            movement_type=request.movement_type,
            movement_date=request.movement_date,
            reference_type=request.reference_type,
            reference_id=request.reference_id,
            actor_id=context.user_id,
            post_journal=request.post_journal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "movement": movement}
