from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import TimelineResponse, TimelineEntryOut
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_read
from app.modules.finance_os.audit_explorer.services.timeline_service import get_timeline

router = APIRouter(tags=["finance-os-audit-timeline"])


@router.get("/timeline/{object_type}/{object_id}", response_model=TimelineResponse)
def object_timeline(object_type: str, object_id: str, context=Depends(build_request_context)) -> TimelineResponse:
    require_audit_read(context.user)
    items = get_timeline(context.org_id, object_type=object_type, object_id=object_id)
    return TimelineResponse(
        request_id=context.request_id,
        object_type=object_type,
        object_id=object_id,
        items=[TimelineEntryOut(**{**i, "event_timestamp": str(i.get("event_timestamp") or "")}) for i in items],
        count=len(items),
    )
