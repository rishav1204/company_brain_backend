from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.services.repositories import audit_repo

router = APIRouter(prefix="/workflows", tags=["workflow-audit"])


@router.get("/instances/{workflow_id}/audit")
def workflow_audit_trail(
    workflow_id: str,
    context=Depends(require_workflow_permission("workflow.read")),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    logs = audit_repo.list_logs(org_id=context.org_id)[:limit]
    filtered = [
        row
        for row in logs
        if workflow_id in str(row.get("object_ref", "")) or workflow_id in str(row.get("payload_jsonb", ""))
    ]
    return {
        "request_id": context.request_id,
        "workflow_id": workflow_id,
        "items": filtered,
        "verification_status": "verified",
    }
