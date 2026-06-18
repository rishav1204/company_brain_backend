from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_receivable.schemas.ar_schema import CustomerAddressRequest, CustomerCreateRequest, CustomerUpdateRequest
from app.modules.erp.accounts_receivable.security.ar_access import enforce_ar_action
from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_admin, require_ar_read
from app.modules.erp.accounts_receivable.services.customer_service import customer_service

router = APIRouter()


@router.post("/customers")
def create_customer(request: CustomerCreateRequest, context=Depends(require_ar_admin)) -> dict:
    enforce_ar_action(context, action="ar.customer.create", object_type="customer", object_id="new")
    try:
        item = customer_service.create_customer(
            context.org_id,
            customer_name=request.customer_name,
            customer_code=request.customer_code,
            customer_type=request.customer_type,
            gstin=request.gstin,
            pan=request.pan,
            email=request.email,
            phone=request.phone,
            credit_limit=request.credit_limit,
            payment_terms_days=request.payment_terms_days,
            receivable_account_id=request.receivable_account_id,
            revenue_account_id=request.revenue_account_id,
            company_id=request.company_id,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/customers")
def list_customers(context=Depends(require_ar_read), status: str | None = Query(default=None)) -> dict:
    items = customer_service.list_customers(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, context=Depends(require_ar_read)) -> dict:
    try:
        item = customer_service.get_customer(context.org_id, customer_id=customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: str, request: CustomerUpdateRequest, context=Depends(require_ar_admin)) -> dict:
    enforce_ar_action(context, action="ar.customer.update", object_type="customer", object_id=customer_id)
    try:
        item = customer_service.update_customer(
            context.org_id,
            customer_id=customer_id,
            customer_name=request.customer_name,
            email=request.email,
            phone=request.phone,
            credit_limit=request.credit_limit,
            payment_terms_days=request.payment_terms_days,
            actor_id=context.user_id,
            require_workflow=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/customers/{customer_id}/addresses")
def add_address(customer_id: str, request: CustomerAddressRequest, context=Depends(require_ar_admin)) -> dict:
    try:
        item = customer_service.add_address(
            context.org_id,
            customer_id=customer_id,
            address_type=request.address_type,
            line1=request.line1,
            line2=request.line2,
            city=request.city,
            state_code=request.state_code,
            postal_code=request.postal_code,
            place_of_supply=request.place_of_supply,
            is_primary=request.is_primary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/customers/{customer_id}/risk")
def customer_risk(customer_id: str, context=Depends(require_ar_read)) -> dict:
    try:
        item = customer_service.get_customer_risk(context.org_id, customer_id=customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
