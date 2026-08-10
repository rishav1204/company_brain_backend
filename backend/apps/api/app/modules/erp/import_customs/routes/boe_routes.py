from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.import_customs.schemas.import_customs_schema import BillOfEntryCreateRequest
from app.modules.erp.import_customs.security.import_customs_guard import (
    require_import_customs_admin,
    require_import_customs_read,
)
from app.modules.erp.import_customs.services.bill_of_entry_service import bill_of_entry_service

router = APIRouter()


@router.post("/bills-of-entry")
def create_bill_of_entry(request: BillOfEntryCreateRequest, context=Depends(require_import_customs_admin)) -> dict:
    try:
        item = bill_of_entry_service.create_boe(
            context.org_id,
            boe_number=request.boe_number,
            boe_date=request.boe_date,
            assessable_value=request.assessable_value,
            customs_duty=request.customs_duty,
            igst_import=request.igst_import,
            company_id=request.company_id,
            branch_id=request.branch_id,
            port_code=request.port_code,
            vendor_id=request.vendor_id,
            po_id=request.po_id,
            currency_code=request.currency_code,
            exchange_rate=request.exchange_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/bills-of-entry")
def list_bills_of_entry(
    context=Depends(require_import_customs_read),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    items = bill_of_entry_service.list_boes(context.org_id, status=status, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/bills-of-entry/{boe_id}")
def get_bill_of_entry(boe_id: str, context=Depends(require_import_customs_read)) -> dict:
    try:
        item = bill_of_entry_service.get_boe(context.org_id, boe_id=boe_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/bills-of-entry/{boe_id}/post")
def post_bill_of_entry(boe_id: str, context=Depends(require_import_customs_admin)) -> dict:
    try:
        item = bill_of_entry_service.post_boe(context.org_id, boe_id=boe_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
