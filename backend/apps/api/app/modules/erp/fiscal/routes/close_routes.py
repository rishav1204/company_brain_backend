from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.fiscal.schemas.fiscal_schema import ChecklistCompleteRequest
from app.modules.erp.fiscal.security.fiscal_guard import require_fiscal_admin, require_fiscal_read
from app.modules.erp.fiscal.services.close_service import close_service

router = APIRouter()


@router.post("/periods/{period_id}/close/init")
def init_close(period_id: str, context=Depends(require_fiscal_admin)) -> dict:
    item = close_service.init_close(context.org_id, period_id=period_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/periods/{period_id}/close/checklist")
def get_checklist(period_id: str, context=Depends(require_fiscal_read)) -> dict:
    items = close_service.list_checklist(context.org_id, period_id=period_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/periods/{period_id}/close/checklist")
def complete_checklist_item(period_id: str, request: ChecklistCompleteRequest, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = close_service.complete_checklist_item(
            context.org_id, period_id=period_id, check_name=request.check_name, actor_id=context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/periods/{period_id}/close/submit")
def submit_close(period_id: str, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = close_service.submit_for_approval(context.org_id, period_id=period_id, started_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/periods/{period_id}/close")
def close_period(period_id: str, context=Depends(require_fiscal_admin)) -> dict:
    try:
        item = close_service.execute_close(context.org_id, period_id=period_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
