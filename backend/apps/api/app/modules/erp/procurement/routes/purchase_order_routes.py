from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.procurement.schemas.procurement_schema import PoCreateRequest
from app.modules.erp.procurement.security.procurement_guard import (
    require_procurement_approve,
    require_procurement_create,
    require_procurement_read,
)
from app.modules.erp.procurement.services.po_service import po_service

router = APIRouter()


@router.post("/po")
def create_po(request: PoCreateRequest, context=Depends(require_procurement_create)) -> dict:
    try:
        item = po_service.create(
            context.org_id,
            vendor_id=request.vendor_id,
            pr_id=request.pr_id,
            po_date=request.po_date,
            expected_delivery_date=request.expected_delivery_date,
            company_id=request.company_id,
            created_by=context.user_id,
            items=[i.model_dump() for i in request.items],
            gst_amount=request.gst_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/po")
def list_po(
    context=Depends(require_procurement_read),
    status: str | None = Query(default=None),
    vendor_id: str | None = Query(default=None),
) -> dict:
    items = po_service.list(context.org_id, status=status, vendor_id=vendor_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/po/{po_id}")
def get_po(po_id: str, context=Depends(require_procurement_read)) -> dict:
    item = po_service.get(context.org_id, po_id=po_id)
    if not item:
        raise HTTPException(status_code=404, detail="PO not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/po/{po_id}/submit")
def submit_po(po_id: str, context=Depends(require_procurement_create)) -> dict:
    try:
        item = po_service.submit_for_approval(context.org_id, po_id=po_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/po/{po_id}/approve")
def approve_po(po_id: str, context=Depends(require_procurement_approve)) -> dict:
    try:
        item = po_service.approve(context.org_id, po_id=po_id, approver_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/po/{po_id}/send")
def send_po(po_id: str, context=Depends(require_procurement_create)) -> dict:
    try:
        item = po_service.send(context.org_id, po_id=po_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/po/{po_id}/close")
def close_po(po_id: str, context=Depends(require_procurement_approve)) -> dict:
    try:
        item = po_service.close(context.org_id, po_id=po_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
