from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.treasury.schemas.treasury_schema import TransferCreateRequest
from app.modules.erp.treasury.security.treasury_access import enforce_treasury_action
from app.modules.erp.treasury.security.treasury_guard import require_treasury_admin, require_treasury_read
from app.modules.erp.treasury.services.transfer_service import transfer_service

router = APIRouter()


@router.post("/transfers")
def create_transfer(request: TransferCreateRequest, context=Depends(require_treasury_admin)) -> dict:
    enforce_treasury_action(context, action="treasury.transfer.create", object_type="transfer", object_id="new")
    try:
        item = transfer_service.create(
            context.org_id,
            source_account_id=request.source_account_id,
            destination_account_id=request.destination_account_id,
            transfer_amount=request.transfer_amount,
            transfer_date=request.transfer_date,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/transfers")
def list_transfers(context=Depends(require_treasury_read)) -> dict:
    items = transfer_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: str, context=Depends(require_treasury_read)) -> dict:
    item = transfer_service.get(context.org_id, transfer_id=transfer_id)
    if not item:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/transfers/{transfer_id}/approve")
def approve_transfer(transfer_id: str, context=Depends(require_treasury_admin)) -> dict:
    enforce_treasury_action(context, action="treasury.transfer.approve", object_type="transfer", object_id=transfer_id, human_approved=True)
    try:
        item = transfer_service.approve_and_execute(context.org_id, transfer_id=transfer_id, approved_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/transfers/{transfer_id}/cancel")
def cancel_transfer(transfer_id: str, context=Depends(require_treasury_admin)) -> dict:
    try:
        item = transfer_service.cancel(context.org_id, transfer_id=transfer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
