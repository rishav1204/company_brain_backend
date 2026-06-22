from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.vouchers.generators import lines_for_voucher
from app.modules.erp.vouchers.schemas.voucher_schema import (
    ContraVoucherCreateRequest,
    JournalVoucherCreateRequest,
    PaymentVoucherCreateRequest,
    PurchaseVoucherCreateRequest,
    ReceiptVoucherCreateRequest,
    SalesVoucherCreateRequest,
)
from app.modules.erp.vouchers.security.voucher_guard import require_voucher_admin
from app.modules.erp.vouchers.services.voucher_service import voucher_service

router = APIRouter()


def _create_typed(
    context,
    *,
    voucher_type: str,
    voucher_date: str,
    narration: str | None,
    company_id: str | None,
    payload: dict,
) -> dict:
    lines = lines_for_voucher(context.org_id, voucher_type=voucher_type, payload=payload)
    return voucher_service.create(
        context.org_id,
        voucher_type=voucher_type,
        voucher_date=voucher_date,
        lines=lines,
        narration=narration,
        company_id=company_id,
        created_by=context.user_id,
        generator_payload=payload,
    )


@router.post("/vouchers/sales")
def create_sales_voucher(request: SalesVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    payload = request.model_dump()
    try:
        item = _create_typed(
            context,
            voucher_type="sales",
            voucher_date=request.voucher_date,
            narration=request.narration,
            company_id=request.company_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/purchase")
def create_purchase_voucher(request: PurchaseVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    payload = request.model_dump()
    try:
        item = _create_typed(
            context,
            voucher_type="purchase",
            voucher_date=request.voucher_date,
            narration=request.narration,
            company_id=request.company_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/payment")
def create_payment_voucher(request: PaymentVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    payload = request.model_dump()
    try:
        item = _create_typed(
            context,
            voucher_type="payment",
            voucher_date=request.voucher_date,
            narration=request.narration,
            company_id=request.company_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/receipt")
def create_receipt_voucher(request: ReceiptVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    payload = request.model_dump()
    try:
        item = _create_typed(
            context,
            voucher_type="receipt",
            voucher_date=request.voucher_date,
            narration=request.narration,
            company_id=request.company_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/contra")
def create_contra_voucher(request: ContraVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    payload = request.model_dump()
    try:
        item = _create_typed(
            context,
            voucher_type="contra",
            voucher_date=request.voucher_date,
            narration=request.narration,
            company_id=request.company_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/journal")
def create_journal_voucher(request: JournalVoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.create(
            context.org_id,
            voucher_type="journal",
            voucher_date=request.voucher_date,
            lines=[line.model_dump() for line in request.lines],
            narration=request.narration,
            company_id=request.company_id,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
