from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.tax.schemas.tax_schema import GstReturnGenerateRequest
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.gst_return_service import gst_return_service

router = APIRouter()


@router.post("/returns/generate")
def generate_return(request: GstReturnGenerateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gst_return", object_id="new")
    try:
        item = gst_return_service.generate_return(
            context.org_id, return_type=request.return_type, return_period=request.return_period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/returns")
def list_returns(context=Depends(require_tax_read), return_type: str | None = None) -> dict:
    items = gst_return_service.list_returns(context.org_id, return_type=return_type)
    return {"request_id": context.request_id, "items": items}


@router.get("/returns/{return_id}")
def get_return(return_id: str, context=Depends(require_tax_read)) -> dict:
    try:
        item = gst_return_service.get_return(context.org_id, return_id=return_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/{return_id}/submit")
def submit_return(return_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gst_return", object_id=return_id)
    item = gst_return_service.submit_for_approval(context.org_id, return_id=return_id, started_by=context.user_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/{return_id}/file")
def file_return(return_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="gst.file", object_type="gst_return", object_id=return_id, human_approved=True)
    try:
        item = gst_return_service.file_return(context.org_id, return_id=return_id, filed_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
