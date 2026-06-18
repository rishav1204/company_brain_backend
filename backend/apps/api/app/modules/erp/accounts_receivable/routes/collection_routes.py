from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_receivable.schemas.ar_schema import ReceiptCompleteRequest, ReceiptRecordRequest
from app.modules.erp.accounts_receivable.security.ar_access import enforce_ar_action
from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_admin, require_ar_read
from app.modules.erp.accounts_receivable.services.ai_collection_service import ai_collection_service
from app.modules.erp.accounts_receivable.services.collection_service import collection_service

router = APIRouter()


@router.post("/collections/receipts")
def record_receipt(request: ReceiptRecordRequest, context=Depends(require_ar_admin)) -> dict:
    enforce_ar_action(
        context, action="ar.receipt.record", object_type="ar_receipt", object_id="new",
        amount=request.amount, company_id=request.company_id,
    )
    try:
        item = collection_service.record_receipt(
            context.org_id,
            customer_id=request.customer_id,
            receipt_date=request.receipt_date,
            amount=request.amount,
            payment_mode=request.payment_mode,
            bank_account_id=request.bank_account_id,
            company_id=request.company_id,
            created_by=context.user_id,
            invoice_allocations=request.invoice_allocations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/collections/receipts/{receipt_id}/complete")
def complete_receipt(
    receipt_id: str,
    request: ReceiptCompleteRequest,
    context=Depends(require_ar_admin),
) -> dict:
    try:
        from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository

        row = receipt_repository.get(context.org_id, receipt_id=receipt_id)
        if not row:
            raise HTTPException(status_code=404, detail="Receipt not found")
        enforce_ar_action(
            context, action="ar.receipt.complete", object_type="ar_receipt", object_id=receipt_id,
            amount=float(row.get("amount") or 0), created_by=row.get("created_by"), human_approved=True,
        )
        item = collection_service.complete_receipt(
            context.org_id, receipt_id=receipt_id, completed_by=context.user_id, auto_post=request.auto_post
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/collections/receipts")
def list_receipts(context=Depends(require_ar_read), customer_id: str | None = Query(default=None)) -> dict:
    items = collection_service.list_receipts(context.org_id, customer_id=customer_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/collections/forecast")
def collection_forecast(context=Depends(require_ar_read)) -> dict:
    item = ai_collection_service.forecast(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/collections/assistant")
def collection_assistant(context=Depends(require_ar_read), limit: int = Query(default=10, ge=1, le=50)) -> dict:
    item = ai_collection_service.assistant(context.org_id, limit=limit)
    return {"request_id": context.request_id, "item": item}
