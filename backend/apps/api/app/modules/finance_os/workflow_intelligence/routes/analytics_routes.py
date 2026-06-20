from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import require_workflow_intelligence_read
from app.modules.finance_os.workflow_intelligence.services.approval_optimization_service import approval_optimization_service
from app.modules.finance_os.workflow_intelligence.services.workflow_pattern_service import workflow_pattern_service

router = APIRouter(tags=["finance-os-workflow-intelligence"])


@router.get("/analytics")
def analytics(
    context=Depends(build_request_context),
    workflow_type: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    require_workflow_intelligence_read(context.user)
    org_id = str(context.org_id)
    return {
        **workflow_pattern_service.analytics(org_id, workflow_type=workflow_type, days=days),
        "queue_overload": approval_optimization_service.queue_overload(org_id),
    }
