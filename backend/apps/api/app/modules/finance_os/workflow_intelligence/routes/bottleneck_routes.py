from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import require_workflow_intelligence_read
from app.modules.finance_os.workflow_intelligence.services.bottleneck_service import bottleneck_service

router = APIRouter(tags=["finance-os-workflow-intelligence"])


@router.get("/bottlenecks")
def list_bottlenecks(
    context=Depends(build_request_context),
    workflow_type: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    require_workflow_intelligence_read(context.user)
    items = bottleneck_service.list_bottlenecks(str(context.org_id), workflow_type=workflow_type, days=days)
    return {"bottlenecks": items, "explanation": bottleneck_service.explain(str(context.org_id), workflow_type=workflow_type)}
