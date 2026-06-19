from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.procurement.schemas.procurement_schema import PrConvertPoRequest, PrCreateRequest
from app.modules.erp.procurement.security.procurement_guard import (
    require_procurement_approve,
    require_procurement_create,
    require_procurement_read,
)
from app.modules.erp.procurement.services.requisition_service import requisition_service

router = APIRouter()


@router.post("/pr")
def create_pr(request: PrCreateRequest, context=Depends(require_procurement_create)) -> dict:
    try:
        item = requisition_service.create(
            context.org_id,
            requester_id=request.requester_id or context.user_id,
            department_id=request.department_id,
            cost_center_id=request.cost_center_id,
            required_date=request.required_date,
            description=request.description,
            company_id=request.company_id,
            created_by=context.user_id,
            items=[i.model_dump() for i in request.items],
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/pr")
def list_pr(context=Depends(require_procurement_read), status: str | None = Query(default=None)) -> dict:
    items = requisition_service.list(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/pr/{pr_id}")
def get_pr(pr_id: str, context=Depends(require_procurement_read)) -> dict:
    item = requisition_service.get(context.org_id, pr_id=pr_id)
    if not item:
        raise HTTPException(status_code=404, detail="PR not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/pr/{pr_id}/submit")
def submit_pr(pr_id: str, context=Depends(require_procurement_create)) -> dict:
    try:
        item = requisition_service.submit(context.org_id, pr_id=pr_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/pr/{pr_id}/approve")
def approve_pr(pr_id: str, context=Depends(require_procurement_approve)) -> dict:
    try:
        item = requisition_service.approve(context.org_id, pr_id=pr_id, approver_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/pr/{pr_id}/cancel")
def cancel_pr(pr_id: str, context=Depends(require_procurement_create)) -> dict:
    try:
        item = requisition_service.cancel(context.org_id, pr_id=pr_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/pr/{pr_id}/convert-po")
def convert_pr_to_po(pr_id: str, request: PrConvertPoRequest, context=Depends(require_procurement_approve)) -> dict:
    try:
        item = requisition_service.convert_to_po(
            context.org_id,
            pr_id=pr_id,
            vendor_id=request.vendor_id,
            actor_id=context.user_id,
            gst_amount=request.gst_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
