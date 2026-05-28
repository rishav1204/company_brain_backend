from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.coa.schemas.account_schema import AccountGroupCreateRequest, AccountGroupUpdateRequest
from app.modules.erp.coa.security.coa_guard import require_finance_admin
from app.modules.erp.coa.services.account_group_service import account_group_service

router = APIRouter()


@router.post("/account-groups")
def create_group(request: AccountGroupCreateRequest, context=Depends(require_finance_admin)) -> dict:
    item = account_group_service.create(
        context.org_id,
        group_name=request.group_name,
        group_code=request.group_code,
        parent_group_id=request.parent_group_id,
        group_type=request.group_type,
        nature=request.nature,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/account-groups")
def list_groups(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = account_group_service.list(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.put("/account-groups/{group_id}")
def update_group(group_id: str, request: AccountGroupUpdateRequest, context=Depends(require_finance_admin)) -> dict:
    item = account_group_service.update(
        context.org_id, group_id=group_id, group_name=request.group_name, parent_group_id=request.parent_group_id
    )
    return {"request_id": context.request_id, "item": item}

