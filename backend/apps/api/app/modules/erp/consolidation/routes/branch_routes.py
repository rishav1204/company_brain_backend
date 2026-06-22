from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.consolidation.security.consolidation_guard import require_consolidation_read
from app.modules.erp.consolidation.services.branch_service import branch_service
from app.modules.erp.consolidation.engine import reporting_engine

router = APIRouter(tags=["consolidation-branches"])


@router.get("/entities/{company_id}/branches")
def list_entity_branches(company_id: str, context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    items = branch_service.list_for_company(context.org_id, company_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/reports/branch/{branch_id}/pnl")
def branch_pnl(
    branch_id: str,
    context=Depends(build_request_context),
    fiscal_period_id: str = Query(...),
) -> dict:
    require_consolidation_read(context)
    rows = reporting_engine.branch_pnl(
        context.org_id, branch_id=branch_id, fiscal_period_id=fiscal_period_id
    )
    return {"request_id": context.request_id, "items": rows}
