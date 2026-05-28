from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.coa.schemas.account_schema import AccountCreateRequest, AccountUpdateRequest
from app.modules.erp.coa.security.coa_guard import require_finance_admin
from app.modules.erp.coa.services.account_service import account_service

router = APIRouter()


@router.post("/accounts")
def create_account(request: AccountCreateRequest, context=Depends(require_finance_admin)) -> dict:
    item = account_service.create(
        context.org_id,
        account_code=request.account_code,
        account_name=request.account_name,
        account_type=request.account_type,
        group_id=request.group_id,
        parent_account_id=request.parent_account_id,
        is_postable=request.is_postable,
        currency_code=request.currency_code,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/accounts")
def list_accounts(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = account_service.list(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/accounts/{account_id}/deactivate")
def deactivate_account(account_id: str, context=Depends(require_finance_admin)) -> dict:
    item = account_service.deactivate(context.org_id, account_id=account_id)
    return {"request_id": context.request_id, "item": item}


@router.put("/accounts/{account_id}")
def update_account(account_id: str, request: AccountUpdateRequest, context=Depends(require_finance_admin)) -> dict:
    item = account_service.update(
        context.org_id,
        account_id=account_id,
        account_name=request.account_name,
        parent_account_id=request.parent_account_id,
    )
    return {"request_id": context.request_id, "item": item}

