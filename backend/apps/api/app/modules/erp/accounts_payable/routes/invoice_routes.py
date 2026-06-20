from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_payable.schemas.ap_schema import (
    AiInvoiceFromDocumentRequest,
    InvoiceApproveRequest,
    InvoiceCreateRequest,
    InvoiceUpdateRequest,
)
from app.modules.erp.accounts_payable.security.ap_access import enforce_ap_action
from app.modules.erp.accounts_payable.security.ap_guard import require_ap_admin, require_ap_read
from app.modules.erp.accounts_payable.services.ai_invoice_service import ai_invoice_service
from app.modules.erp.accounts_payable.services.invoice_service import invoice_service

router = APIRouter()


@router.post("/invoices")
def create_invoice(request: InvoiceCreateRequest, context=Depends(require_ap_admin)) -> dict:
    enforce_ap_action(
        context,
        action="ap.invoice.create",
        object_type="ap_invoice",
        object_id="new",
        amount=request.total_amount,
        company_id=request.company_id,
    )
    try:
        item = invoice_service.create_invoice(
            context.org_id,
            vendor_id=request.vendor_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            invoice_amount=request.invoice_amount,
            gst_amount=request.gst_amount,
            total_amount=request.total_amount,
            source_document_id=request.source_document_id,
            company_id=request.company_id,
            created_by=context.user_id,
            expense_account_id=request.expense_account_id,
            lines=[l.model_dump() for l in request.lines],
            purchase_order_id=request.purchase_order_id,
            goods_receipt_id=request.goods_receipt_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/invoices")
def list_invoices(
    context=Depends(require_ap_read),
    status: str | None = Query(default=None),
    vendor_id: str | None = Query(default=None),
) -> dict:
    items = invoice_service.list_invoices(context.org_id, status=status, vendor_id=vendor_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, context=Depends(require_ap_read)) -> dict:
    try:
        item = invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: str,
    request: InvoiceUpdateRequest,
    context=Depends(require_ap_admin),
) -> dict:
    try:
        existing = invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
        enforce_ap_action(
            context,
            action="ap.invoice.update",
            object_type="ap_invoice",
            object_id=invoice_id,
            amount=float((existing.get("invoice") or {}).get("total_amount") or 0),
            created_by=(existing.get("invoice") or {}).get("created_by"),
            company_id=(existing.get("invoice") or {}).get("company_id"),
        )
        item = invoice_service.update_invoice(
            context.org_id,
            invoice_id=invoice_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            invoice_amount=request.invoice_amount,
            gst_amount=request.gst_amount,
            total_amount=request.total_amount,
            expense_account_id=request.expense_account_id,
            lines=[l.model_dump() for l in request.lines] if request.lines else None,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/submit")
def submit_invoice(invoice_id: str, context=Depends(require_ap_admin)) -> dict:
    try:
        existing = invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
        enforce_ap_action(
            context,
            action="ap.invoice.submit",
            object_type="ap_invoice",
            object_id=invoice_id,
            amount=float((existing.get("invoice") or {}).get("total_amount") or 0),
            created_by=(existing.get("invoice") or {}).get("created_by"),
            company_id=(existing.get("invoice") or {}).get("company_id"),
        )
        item = invoice_service.submit_for_approval(context.org_id, invoice_id=invoice_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/confirm-review")
def confirm_review(invoice_id: str, context=Depends(require_ap_admin)) -> dict:
    try:
        item = invoice_service.confirm_review(context.org_id, invoice_id=invoice_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(
    invoice_id: str,
    request: InvoiceApproveRequest,
    context=Depends(require_ap_admin),
) -> dict:
    try:
        existing = invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
        enforce_ap_action(
            context,
            action="ap.invoice.approve",
            object_type="ap_invoice",
            object_id=invoice_id,
            amount=float((existing.get("invoice") or {}).get("total_amount") or 0),
            created_by=(existing.get("invoice") or {}).get("created_by"),
            company_id=(existing.get("invoice") or {}).get("company_id"),
            human_approved=True,
        )
        item = invoice_service.approve(
            context.org_id,
            invoice_id=invoice_id,
            approver_id=context.user_id,
            expense_account_id=request.expense_account_id,
            auto_post=request.auto_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: str, context=Depends(require_ap_admin)) -> dict:
    try:
        item = invoice_service.cancel(context.org_id, invoice_id=invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/ai/from-document")
def create_ai_invoice(request: AiInvoiceFromDocumentRequest, context=Depends(require_ap_admin)) -> dict:
    try:
        if request.document_id and not request.extracted_data:
            item = ai_invoice_service.create_from_document(
                context.org_id,
                document_id=request.document_id,
                created_by=context.user_id,
                company_id=request.company_id,
            )
        else:
            item = ai_invoice_service.create_from_extraction(
                context.org_id,
                extracted_data=request.extracted_data or {},
                source_document_id=request.document_id,
                created_by=context.user_id,
                company_id=request.company_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
