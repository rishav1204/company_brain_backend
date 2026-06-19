from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.expenses.schemas.expense_schema import (
    ClaimApproveRequest,
    ClaimCreateRequest,
    ClaimRejectRequest,
)
from app.modules.erp.expenses.security.expense_guard import (
    require_expense_approve,
    require_expense_create,
    require_expense_read,
)
from app.modules.erp.expenses.services.claim_service import claim_service

router = APIRouter()


@router.post("/claims")
def create_claim(request: ClaimCreateRequest, context=Depends(require_expense_create)) -> dict:
    try:
        item = claim_service.create(
            context.org_id,
            employee_id=request.employee_id or context.user_id,
            claim_date=request.claim_date,
            expense_category=request.expense_category,
            company_id=request.company_id,
            cost_center_id=request.cost_center_id,
            department_id=request.department_id,
            created_by=context.user_id,
            items=[i.model_dump() for i in request.items],
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/claims")
def list_claims(
    context=Depends(require_expense_read),
    employee_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    items = claim_service.list(context.org_id, employee_id=employee_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, context=Depends(require_expense_read)) -> dict:
    item = claim_service.get(context.org_id, claim_id=claim_id)
    if not item:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/claims/{claim_id}/submit")
def submit_claim(claim_id: str, context=Depends(require_expense_create)) -> dict:
    try:
        item = claim_service.submit(context.org_id, claim_id=claim_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/claims/{claim_id}/approve")
def approve_claim(
    claim_id: str,
    request: ClaimApproveRequest,
    context=Depends(require_expense_approve),
) -> dict:
    try:
        item = claim_service.approve(
            context.org_id,
            claim_id=claim_id,
            approver_id=context.user_id,
            auto_reimburse=request.auto_reimburse,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: str, request: ClaimRejectRequest, context=Depends(require_expense_approve)) -> dict:
    try:
        item = claim_service.reject(
            context.org_id, claim_id=claim_id, actor_id=context.user_id, reason=request.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/claims/{claim_id}/cancel")
def cancel_claim(claim_id: str, context=Depends(require_expense_create)) -> dict:
    try:
        item = claim_service.cancel(context.org_id, claim_id=claim_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
