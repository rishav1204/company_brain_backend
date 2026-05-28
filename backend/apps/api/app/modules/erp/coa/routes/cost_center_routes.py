from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.coa.schemas.account_schema import CostCenterCreateRequest, CostCenterUpdateRequest
from app.modules.erp.coa.security.coa_guard import require_finance_admin
from app.modules.erp.coa.services.cost_center_service import cost_center_service

router = APIRouter()


@router.post("/cost-centers")
def create_cost_center(request: CostCenterCreateRequest, context=Depends(require_finance_admin)) -> dict:
    item = cost_center_service.create(
        context.org_id,
        cost_center_code=request.cost_center_code,
        cost_center_name=request.cost_center_name,
        parent_cost_center_id=request.parent_cost_center_id,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/cost-centers")
def list_cost_centers(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = cost_center_service.list(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/cost-centers/{cost_center_id}/deactivate")
def deactivate_cost_center(cost_center_id: str, context=Depends(require_finance_admin)) -> dict:
    item = cost_center_service.deactivate(context.org_id, cost_center_id=cost_center_id)
    return {"request_id": context.request_id, "item": item}


@router.put("/cost-centers/{cost_center_id}")
def update_cost_center(cost_center_id: str, request: CostCenterUpdateRequest, context=Depends(require_finance_admin)) -> dict:
    item = cost_center_service.update(
        context.org_id,
        cost_center_id=cost_center_id,
        cost_center_name=request.cost_center_name,
        parent_cost_center_id=request.parent_cost_center_id,
    )
    return {"request_id": context.request_id, "item": item}

