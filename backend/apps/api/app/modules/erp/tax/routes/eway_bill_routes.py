from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.tax.schemas.tax_schema import EwayBillGenerateRequest, EwayBillCancelRequest
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.eway_bill_service import eway_bill_service

router = APIRouter()


@router.post("/eway-bill/generate")
def generate_eway_bill(request: EwayBillGenerateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="eway_bill", object_id=request.source_id)
    try:
        item = eway_bill_service.generate(
            context.org_id,
            source_type=request.source_type,
            source_id=request.source_id,
            distance_km=request.distance_km,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/eway-bill/{eway_bill_id}")
def get_eway_bill(eway_bill_id: str, context=Depends(require_tax_read)) -> dict:
    item = eway_bill_service.get(context.org_id, eway_bill_id=eway_bill_id)
    if not item:
        raise HTTPException(status_code=404, detail="E-way bill not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/eway-bill/{eway_bill_id}/cancel")
def cancel_eway_bill(eway_bill_id: str, request: EwayBillCancelRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="eway_bill", object_id=eway_bill_id)
    try:
        item = eway_bill_service.cancel(context.org_id, eway_bill_id=eway_bill_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
