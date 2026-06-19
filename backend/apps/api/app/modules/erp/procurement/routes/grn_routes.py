from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.procurement.schemas.procurement_schema import GrnCreateRequest
from app.modules.erp.procurement.security.procurement_guard import require_procurement_receive, require_procurement_read
from app.modules.erp.procurement.services.grn_service import grn_service

router = APIRouter()


@router.post("/grn")
def create_grn(request: GrnCreateRequest, context=Depends(require_procurement_receive)) -> dict:
    try:
        item = grn_service.create(
            context.org_id,
            po_id=request.po_id,
            received_by=context.user_id,
            received_date=request.received_date,
            items=[i.model_dump() for i in request.items],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/grn/{grn_id}")
def get_grn(grn_id: str, context=Depends(require_procurement_read)) -> dict:
    item = grn_service.get(context.org_id, grn_id=grn_id)
    if not item:
        raise HTTPException(status_code=404, detail="GRN not found")
    return {"request_id": context.request_id, "item": item}


@router.get("/po/{po_id}/grn")
def list_grn_for_po(po_id: str, context=Depends(require_procurement_read)) -> dict:
    items = grn_service.list_for_po(context.org_id, po_id=po_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/grn/{grn_id}/submit")
def submit_grn(grn_id: str, context=Depends(require_procurement_receive)) -> dict:
    try:
        item = grn_service.submit_for_confirmation(context.org_id, grn_id=grn_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/grn/{grn_id}/confirm")
def confirm_grn(grn_id: str, context=Depends(require_procurement_receive)) -> dict:
    try:
        item = grn_service.confirm(context.org_id, grn_id=grn_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
