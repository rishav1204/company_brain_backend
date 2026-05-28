from fastapi import APIRouter, Depends, Query

from app.modules.platform.governance.api.deps import require_auditor_read
from app.modules.platform.governance.services.audit_service import audit_service
from app.schemas.audit import AuditLogItem, AuditLogListResponse

router = APIRouter(tags=["governance-audit"])


@router.get("/audit/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    context=Depends(require_auditor_read),
    event_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    rows = audit_service.list_logs(
        context.org_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        trace_id=trace_id,
        limit=limit,
        offset=offset,
    )
    items = [AuditLogItem(**{**row, "event_type": row.get("event_type") or row.get("action", "")}) for row in rows]
    return AuditLogListResponse(
        request_id=context.request_id,
        items=items,
        confidence=1.0,
        verification_status="immutable_log",
    )


@router.get("/audit/timeline/{entity_type}/{entity_id}")
def entity_timeline(entity_type: str, entity_id: str, context=Depends(require_auditor_read)) -> dict:
    items = audit_service.entity_timeline(context.org_id, entity_type=entity_type, entity_id=entity_id)
    return {"request_id": context.request_id, "entity_type": entity_type, "entity_id": entity_id, "items": items}


@router.get("/audit/export")
def export_audit_logs(context=Depends(require_auditor_read), limit: int = Query(default=1000, le=5000)) -> dict:
    items = audit_service.list_logs(context.org_id, limit=limit)
    return {"request_id": context.request_id, "format": "json", "count": len(items), "items": items}
