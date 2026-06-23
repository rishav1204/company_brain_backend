from fastapi import APIRouter, Depends

from app.modules.core.iam.middleware.permission_guard import require_permission
from app.schemas.audit import AuditLogItem, AuditLogListResponse
from app.services.repositories import audit_repo

router = APIRouter(tags=["audit"])


@router.get("/audit/logs", response_model=AuditLogListResponse)
def list_audit_logs(context=Depends(require_permission("audit.read"))) -> AuditLogListResponse:
    rows = [AuditLogItem(**row) for row in audit_repo.list_logs(org_id=context.org_id)]
    return AuditLogListResponse(
        request_id=context.request_id,
        items=rows,
        confidence=1.0,
        verification_status="immutable_log",
    )
