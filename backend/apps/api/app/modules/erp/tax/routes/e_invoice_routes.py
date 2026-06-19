from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.tax.schemas.tax_schema import EInvoiceCancelRequest
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.e_invoice_service import e_invoice_service

router = APIRouter()


@router.post("/e-invoice/{invoice_id}/generate")
def generate_e_invoice(invoice_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="e_invoice", object_id=invoice_id)
    try:
        item = e_invoice_service.generate(context.org_id, ar_invoice_id=invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/e-invoice/{invoice_id}")
def get_e_invoice(invoice_id: str, context=Depends(require_tax_read)) -> dict:
    item = e_invoice_service.get(context.org_id, ar_invoice_id=invoice_id)
    if not item:
        raise HTTPException(status_code=404, detail="E-invoice not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/e-invoice/{invoice_id}/cancel")
def cancel_e_invoice(invoice_id: str, request: EInvoiceCancelRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="e_invoice", object_id=invoice_id)
    try:
        item = e_invoice_service.cancel(context.org_id, ar_invoice_id=invoice_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
