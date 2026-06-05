from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_payable.schemas.ap_schema import VendorBankAccountRequest, VendorCreateRequest, VendorUpdateRequest
from app.modules.erp.accounts_payable.security.ap_access import enforce_ap_action
from app.modules.erp.accounts_payable.security.ap_guard import require_ap_admin, require_ap_read
from app.modules.erp.accounts_payable.services.vendor_service import vendor_service

router = APIRouter()


@router.post("/vendors")
def create_vendor(request: VendorCreateRequest, context=Depends(require_ap_admin)) -> dict:
    enforce_ap_action(context, action="ap.vendor.create", object_type="vendor", object_id="new")
    try:
        item = vendor_service.create_vendor(
            context.org_id,
            vendor_name=request.vendor_name,
            vendor_code=request.vendor_code,
            gstin=request.gstin,
            pan=request.pan,
            email=request.email,
            phone=request.phone,
            payment_terms_days=request.payment_terms_days,
            payable_account_id=request.payable_account_id,
            company_id=request.company_id,
            created_by=context.user_id,
            early_payment_discount_rate=request.early_payment_discount_rate,
            early_payment_discount_days=request.early_payment_discount_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/vendors")
def list_vendors(context=Depends(require_ap_read), status: str | None = Query(default=None)) -> dict:
    items = vendor_service.list_vendors(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: str, context=Depends(require_ap_read)) -> dict:
    try:
        item = vendor_service.get_vendor(context.org_id, vendor_id=vendor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/vendors/{vendor_id}")
def update_vendor(vendor_id: str, request: VendorUpdateRequest, context=Depends(require_ap_admin)) -> dict:
    enforce_ap_action(context, action="ap.vendor.update", object_type="vendor", object_id=vendor_id)
    try:
        item = vendor_service.update_vendor(
            context.org_id,
            vendor_id=vendor_id,
            vendor_name=request.vendor_name,
            email=request.email,
            phone=request.phone,
            payment_terms_days=request.payment_terms_days,
            payable_account_id=request.payable_account_id,
            early_payment_discount_rate=request.early_payment_discount_rate,
            early_payment_discount_days=request.early_payment_discount_days,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vendors/{vendor_id}/deactivate")
def deactivate_vendor(vendor_id: str, context=Depends(require_ap_admin)) -> dict:
    enforce_ap_action(context, action="ap.vendor.deactivate", object_type="vendor", object_id=vendor_id)
    try:
        item = vendor_service.deactivate_vendor(context.org_id, vendor_id=vendor_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/vendors/{vendor_id}/risk")
def vendor_risk(vendor_id: str, context=Depends(require_ap_read)) -> dict:
    try:
        item = vendor_service.get_vendor_risk(context.org_id, vendor_id=vendor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vendors/{vendor_id}/bank-accounts")
def add_bank_account(vendor_id: str, request: VendorBankAccountRequest, context=Depends(require_ap_admin)) -> dict:
    try:
        item = vendor_service.add_bank_account(
            context.org_id,
            vendor_id=vendor_id,
            account_number=request.account_number,
            ifsc_code=request.ifsc_code,
            bank_name=request.bank_name,
            is_primary=request.is_primary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
