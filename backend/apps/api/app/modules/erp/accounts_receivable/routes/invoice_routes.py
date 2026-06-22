from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_receivable.schemas.ar_schema import SalesInvoiceCreateRequest, SalesInvoiceIssueRequest, WriteOffRequest
from app.modules.erp.accounts_receivable.security.ar_access import enforce_ar_action
from app.modules.erp.accounts_receivable.security.ar_guard import require_ar_admin, require_ar_read
from app.modules.erp.accounts_receivable.services.sales_invoice_service import sales_invoice_service

router = APIRouter()


@router.post("/invoices")
def create_invoice(request: SalesInvoiceCreateRequest, context=Depends(require_ar_admin)) -> dict:
    enforce_ar_action(
        context, action="ar.invoice.create", object_type="ar_invoice", object_id="new",
        amount=request.total_amount, company_id=request.company_id,
    )
    try:
        item = sales_invoice_service.create_invoice(
            context.org_id,
            customer_id=request.customer_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            subtotal=request.subtotal,
            gst_amount=request.gst_amount,
            total_amount=request.total_amount,
            cgst=request.cgst,
            sgst=request.sgst,
            igst=request.igst,
            gst_rate=request.gst_rate,
            export_zero_rated=request.export_zero_rated,
            company_id=request.company_id,
            created_by=context.user_id,
            contract_months=request.contract_months,
            lines=[l.model_dump() for l in request.lines],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/invoices")
def list_invoices(
    context=Depends(require_ar_read),
    status: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
) -> dict:
    items = sales_invoice_service.list_invoices(context.org_id, status=status, customer_id=customer_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, context=Depends(require_ar_read)) -> dict:
    try:
        item = sales_invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/issue")
def issue_invoice(
    invoice_id: str,
    request: SalesInvoiceIssueRequest,
    context=Depends(require_ar_admin),
) -> dict:
    try:
        existing = sales_invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
        enforce_ar_action(
            context, action="ar.invoice.issue", object_type="ar_invoice", object_id=invoice_id,
            amount=float((existing.get("invoice") or {}).get("total_amount") or 0),
            created_by=(existing.get("invoice") or {}).get("created_by"),
            company_id=(existing.get("invoice") or {}).get("company_id"),
            human_approved=True,
        )
        item = sales_invoice_service.issue_invoice(
            context.org_id,
            invoice_id=invoice_id,
            issued_by=context.user_id,
            auto_post=request.auto_post,
            force_credit_approval=request.force_credit_approval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: str, context=Depends(require_ar_admin)) -> dict:
    try:
        item = sales_invoice_service.cancel_invoice(context.org_id, invoice_id=invoice_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/write-off")
def write_off_invoice(
    invoice_id: str,
    request: WriteOffRequest,
    context=Depends(require_ar_admin),
) -> dict:
    try:
        existing = sales_invoice_service.get_invoice(context.org_id, invoice_id=invoice_id)
        enforce_ar_action(
            context, action="ar.invoice.writeoff", object_type="ar_invoice", object_id=invoice_id,
            amount=float((existing.get("invoice") or {}).get("total_amount") or 0),
            created_by=(existing.get("invoice") or {}).get("created_by"),
            human_approved=True,
        )
        item = sales_invoice_service.write_off_invoice(
            context.org_id,
            invoice_id=invoice_id,
            approver_id=context.user_id,
            bad_debt_account_id=request.bad_debt_account_id,
            auto_post=request.auto_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/credit-note")
def create_ar_credit_note(
    invoice_id: str,
    request: SalesInvoiceCreateRequest,
    context=Depends(require_ar_admin),
) -> dict:
    from app.modules.erp.accounts_receivable.services.note_service import ar_note_service

    try:
        item = ar_note_service.create_credit_note(
            context.org_id,
            reference_invoice_id=invoice_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            amount=request.subtotal,
            gst_amount=request.gst_amount,
            total_amount=request.total_amount,
            created_by=context.user_id,
            narration=request.invoice_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/invoices/{invoice_id}/debit-note")
def create_ar_debit_note(
    invoice_id: str,
    request: SalesInvoiceCreateRequest,
    context=Depends(require_ar_admin),
) -> dict:
    from app.modules.erp.accounts_receivable.services.note_service import ar_note_service

    try:
        item = ar_note_service.create_debit_note(
            context.org_id,
            reference_invoice_id=invoice_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            amount=request.subtotal,
            gst_amount=request.gst_amount,
            total_amount=request.total_amount,
            created_by=context.user_id,
            narration=request.invoice_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
