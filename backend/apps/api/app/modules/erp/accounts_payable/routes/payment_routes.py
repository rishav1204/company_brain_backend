from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.accounts_payable.events.ap_events import emit_payment_scheduled
from app.modules.erp.accounts_payable.schemas.ap_schema import (
    PaymentExecuteRequest,
    PaymentRecommendationsRequest,
    PaymentScheduleProposalRequest,
    PaymentScheduleRequest,
)
from app.modules.erp.accounts_payable.security.ap_access import enforce_ap_action
from app.modules.erp.accounts_payable.security.ap_guard import require_ap_admin, require_ap_read
from app.modules.erp.accounts_payable.services.payment_service import payment_service
from app.modules.erp.accounts_payable.services.payment_scheduler_service import payment_scheduler_service

router = APIRouter()


@router.post("/payments/schedule")
def schedule_payment(request: PaymentScheduleRequest, context=Depends(require_ap_admin)) -> dict:
    enforce_ap_action(
        context,
        action="ap.payment.schedule",
        object_type="ap_payment",
        object_id="new",
        amount=request.amount,
        company_id=request.company_id,
    )
    try:
        item = payment_service.schedule_payment(
            context.org_id,
            vendor_id=request.vendor_id,
            payment_date=request.payment_date,
            amount=request.amount,
            invoice_allocations=request.invoice_allocations,
            bank_account_id=request.bank_account_id,
            company_id=request.company_id,
            created_by=context.user_id,
        )
        emit_payment_scheduled(
            context.org_id,
            payment_id=str(item["id"]),
            amount=request.amount,
            vendor_id=request.vendor_id,
            bank_account_id=request.bank_account_id,
            payment_date=request.payment_date,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/payments/{payment_id}/execute")
def execute_payment(
    payment_id: str,
    request: PaymentExecuteRequest,
    context=Depends(require_ap_admin),
) -> dict:
    try:
        from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

        row = payment_repository.get(context.org_id, payment_id=payment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Payment not found")
        enforce_ap_action(
            context,
            action="ap.payment.execute",
            object_type="ap_payment",
            object_id=payment_id,
            amount=float((row or {}).get("amount") or 0),
            created_by=(row or {}).get("created_by"),
            human_approved=True,
        )
        from app.core.config import settings
        if not settings.allow_direct_ap_execute and settings.app_env not in ("dev", "test"):
            raise HTTPException(
                status_code=409,
                detail="Direct AP execute deprecated — use POST /erp/banking/payments/{id}/execute after treasury approval",
            )
        item = payment_service.execute_payment(
            context.org_id,
            payment_id=payment_id,
            executed_by=context.user_id,
            payable_account_id=request.payable_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/payments")
def list_payments(context=Depends(require_ap_read), status: str | None = Query(default=None)) -> dict:
    items = payment_service.list_payments(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/payments/propose-schedule")
def propose_payment_schedule(request: PaymentScheduleProposalRequest, context=Depends(require_ap_admin)) -> dict:
    item = payment_scheduler_service.propose_schedule(
        context.org_id,
        cash_available=request.cash_available,
        as_of_date=request.as_of_date,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/payments/recommendations")
def payment_recommendations(
    context=Depends(require_ap_admin),
    cash_available: float = Query(gt=0),
    as_of_date: str | None = Query(default=None),
) -> dict:
    item = payment_scheduler_service.payment_recommendations(
        context.org_id,
        cash_available=cash_available,
        as_of_date=as_of_date,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/payments/recommendations")
def payment_recommendations_post(
    request: PaymentRecommendationsRequest,
    context=Depends(require_ap_admin),
) -> dict:
    item = payment_scheduler_service.payment_recommendations(
        context.org_id,
        cash_available=request.cash_available,
        as_of_date=request.as_of_date,
    )
    return {"request_id": context.request_id, "item": item}
