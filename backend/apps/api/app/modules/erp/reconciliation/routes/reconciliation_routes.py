from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.modules.erp.reconciliation.schemas.reconciliation_schema import (
    ExceptionAssignRequest,
    ReconciliationAdjustmentCreate,
    ReconciliationApproveRequest,
    ReconciliationCopilotRequest,
    ReconciliationMatchRequest,
)
from app.modules.erp.reconciliation.security.reconciliation_guard import require_reconciliation_admin, require_reconciliation_read
from app.modules.erp.reconciliation.services.adjustment_service import adjustment_service
from app.modules.erp.reconciliation.services.bank_match_service import bank_match_service
from app.modules.erp.reconciliation.services.customer_match_service import customer_match_service
from app.modules.erp.reconciliation.services.exception_service import exception_service
from app.modules.erp.reconciliation.services.reconciliation_service import reconciliation_service
from app.modules.erp.reconciliation.services.vendor_match_service import vendor_match_service
from app.modules.erp.treasury.security.treasury_access import enforce_treasury_action

router = APIRouter()


@router.get("/bank")
def bank_workbench(
    context=Depends(require_reconciliation_read),
    bank_account_id: str | None = Query(default=None),
) -> dict:
    items = bank_match_service.list_workbench(context.org_id, bank_account_id=bank_account_id)
    return {"request_id": context.request_id, **items}


@router.post("/suggest")
def suggest_reconciliation(
    context=Depends(require_reconciliation_admin),
    bank_account_id: str | None = Query(default=None),
) -> dict:
    enforce_treasury_action(context, action="treasury.reconciliation.suggest", object_type="reconciliation", object_id="new")
    items = reconciliation_service.suggest_matches(context.org_id, bank_account_id=bank_account_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/match")
def manual_match(request: ReconciliationMatchRequest, context=Depends(require_reconciliation_admin)) -> dict:
    enforce_treasury_action(context, action="treasury.reconciliation.match", object_type="reconciliation", object_id="new")
    try:
        item = reconciliation_service.manual_match(
            context.org_id,
            bank_transaction_ids=request.bank_transaction_ids,
            entity_allocations=request.entity_allocations,
            ledger_entry_id=request.ledger_entry_id,
            actor_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/")
def list_reconciliation(context=Depends(require_reconciliation_read), status: str | None = Query(default="suggested")) -> dict:
    items = reconciliation_service.list_suggestions(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/{reconciliation_id}/approve")
def approve_reconciliation(
    reconciliation_id: str,
    request: ReconciliationApproveRequest,
    context=Depends(require_reconciliation_admin),
) -> dict:
    enforce_treasury_action(
        context, action="treasury.reconciliation.approve", object_type="reconciliation",
        object_id=reconciliation_id, human_approved=True,
    )
    try:
        item = reconciliation_service.approve_match(
            context.org_id,
            reconciliation_id=reconciliation_id,
            approved_by=context.user_id,
            ledger_entry_id=request.ledger_entry_id,
            roles=context.roles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/{reconciliation_id}/reject")
def reject_reconciliation(reconciliation_id: str, context=Depends(require_reconciliation_admin)) -> dict:
    enforce_treasury_action(context, action="treasury.reconciliation.reject", object_type="reconciliation", object_id=reconciliation_id)
    try:
        item = reconciliation_service.reject_match(context.org_id, reconciliation_id=reconciliation_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/{reconciliation_id}/escalate")
def escalate_reconciliation(reconciliation_id: str, context=Depends(require_reconciliation_admin)) -> dict:
    enforce_treasury_action(context, action="treasury.reconciliation.escalate", object_type="reconciliation", object_id=reconciliation_id)
    try:
        item = reconciliation_service.escalate_to_manual_review(
            context.org_id, reconciliation_id=reconciliation_id, actor_id=context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/exceptions")
def list_exceptions(context=Depends(require_reconciliation_read), status: str | None = Query(default="open")) -> dict:
    items = exception_service.list(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/exceptions/{exception_id}/assign")
def assign_exception(exception_id: str, request: ExceptionAssignRequest, context=Depends(require_reconciliation_admin)) -> dict:
    try:
        item = exception_service.assign(context.org_id, exception_id=exception_id, assigned_to=request.assigned_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/adjustment")
def create_adjustment(request: ReconciliationAdjustmentCreate, context=Depends(require_reconciliation_admin)) -> dict:
    try:
        item = adjustment_service.create(
            context.org_id,
            bank_transaction_id=request.bank_transaction_id,
            reconciliation_id=request.reconciliation_id,
            adjustment_type=request.adjustment_type,
            amount=request.amount,
            expense_account_id=request.expense_account_id,
            bank_account_id=request.bank_account_id,
            description=request.description,
            created_by=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/adjustment/{adjustment_id}/approve")
def approve_adjustment(adjustment_id: str, context=Depends(require_reconciliation_admin)) -> dict:
    from app.modules.erp.reconciliation.repositories.adjustment_repository import adjustment_repository
    from app.modules.platform.governance.engine.policy_engine import evaluate

    adj = adjustment_repository.get(context.org_id, adjustment_id=adjustment_id)
    amount = float((adj or {}).get("amount") or 0)
    policy = evaluate(
        context.org_id,
        action="reconciliation.override",
        attrs={"amount": amount, "adjustment_id": adjustment_id},
        roles=context.roles,
        actor_user_id=context.user_id,
        object_type="reconciliation_adjustment",
        object_id=adjustment_id,
        dry_run=True,
    )
    if not policy.allowed:
        raise HTTPException(status_code=403, detail=policy.reason or "policy_denied")
    try:
        item = adjustment_service.approve_and_post(
            context.org_id, adjustment_id=adjustment_id, approved_by=context.user_id, roles=context.roles
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vendor/{vendor_id}/match/apply")
def apply_vendor_matches(vendor_id: str, context=Depends(require_reconciliation_read)) -> dict:
    item = vendor_match_service.apply_suggested_matches(context.org_id, vendor_id=vendor_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/vendor/{vendor_id}/match")
def vendor_subledger_match(vendor_id: str, context=Depends(require_reconciliation_read)) -> dict:
    item = vendor_match_service.match_payments_to_invoices(context.org_id, vendor_id=vendor_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/customer/{customer_id}/match")
def customer_subledger_match(customer_id: str, context=Depends(require_reconciliation_read)) -> dict:
    item = customer_match_service.match_receipts_to_invoices(context.org_id, customer_id=customer_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/customer/{customer_id}/match/apply")
def apply_customer_matches(customer_id: str, context=Depends(require_reconciliation_read)) -> dict:
    item = customer_match_service.apply_suggested_matches(context.org_id, customer_id=customer_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/vendor/{vendor_id}")
def vendor_reconciliation(vendor_id: str, context=Depends(require_reconciliation_read)) -> dict:
    summary = vendor_match_service.vendor_summary(context.org_id, vendor_id=vendor_id)
    return {"request_id": context.request_id, **summary}


@router.get("/customer/{customer_id}")
def customer_reconciliation(customer_id: str, context=Depends(require_reconciliation_read)) -> dict:
    summary = customer_match_service.customer_summary(context.org_id, customer_id=customer_id)
    return {"request_id": context.request_id, **summary}


@router.post("/copilot")
def reconciliation_copilot(request: ReconciliationCopilotRequest, context=Depends(require_reconciliation_read)) -> dict:
    workbench = bank_match_service.list_workbench(context.org_id)
    suggestions = reconciliation_service.list_suggestions(context.org_id, status="suggested")
    exceptions = exception_service.list(context.org_id, status="open")
    answer = intelligence_registry.reconciliation().answer_question(
        question=request.question,
        unreconciled=workbench.get("unreconciled"),
        exceptions=exceptions,
        suggestions=suggestions,
    )
    return {"request_id": context.request_id, **answer}
