from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.vouchers.schemas.voucher_schema import VoucherApproveRequest, VoucherCreateRequest
from app.modules.erp.vouchers.security.voucher_guard import require_voucher_admin, require_voucher_read
from app.modules.erp.vouchers.services.voucher_service import voucher_service

router = APIRouter()


@router.post("/vouchers")
def create_voucher(request: VoucherCreateRequest, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.create(
            context.org_id,
            voucher_type=request.voucher_type,
            voucher_date=request.voucher_date,
            lines=[line.model_dump() for line in request.lines],
            narration=request.narration,
            company_id=request.company_id,
            branch_id=request.branch_id,
            reference_type=request.reference_type,
            reference_id=request.reference_id,
            created_by=context.user_id,
            idempotency_key=request.idempotency_key,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/vouchers")
def list_vouchers(
    context=Depends(require_voucher_read),
    voucher_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = voucher_service.list(
        context.org_id,
        voucher_type=voucher_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/vouchers/{voucher_id}")
def get_voucher(voucher_id: str, context=Depends(require_voucher_read)) -> dict:
    try:
        item = voucher_service.get(context.org_id, voucher_id=voucher_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/validate")
def validate_voucher(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.validate(context.org_id, voucher_id=voucher_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/submit")
def submit_voucher(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.submit_for_approval(
            context.org_id, voucher_id=voucher_id, submitted_by=context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/approve")
def approve_voucher(
    voucher_id: str,
    request: VoucherApproveRequest,
    context=Depends(require_voucher_admin),
) -> dict:
    try:
        item = voucher_service.approve(
            context.org_id,
            voucher_id=voucher_id,
            approver_id=context.user_id,
            auto_post=request.auto_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/generate-journal")
def generate_journal(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.generate_journal(
            context.org_id, voucher_id=voucher_id, approver_id=context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/post")
def post_voucher(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.post(context.org_id, voucher_id=voucher_id, posted_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/cancel")
def cancel_voucher(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.cancel(context.org_id, voucher_id=voucher_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/vouchers/{voucher_id}/reverse")
def reverse_voucher(voucher_id: str, context=Depends(require_voucher_admin)) -> dict:
    try:
        item = voucher_service.reverse(context.org_id, voucher_id=voucher_id, reversed_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
