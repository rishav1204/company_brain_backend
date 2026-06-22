from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.finance_os.audit_explorer.services.workflow_trace_service import get_approval_chain

router = APIRouter(prefix="/workflows", tags=["workflow-audit"])


@router.get("/instances/{workflow_id}/audit")
def workflow_audit_trail(
    workflow_id: str,
    context=Depends(require_workflow_permission("workflow.read")),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    result = get_approval_chain(context.org_id, workflow_id)
    items = (result.get("approvals") or []) + (result.get("steps") or [])
    return {
        "request_id": context.request_id,
        "workflow_id": workflow_id,
        "items": items[:limit],
        "verification_status": "verified",
        "source": "finance_os.audit_explorer",
    }
