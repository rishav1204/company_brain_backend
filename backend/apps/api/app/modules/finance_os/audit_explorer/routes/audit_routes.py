from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import SearchResponse, ExploreResponse
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_read
from app.modules.finance_os.audit_explorer.services.audit_search_service import search
from app.modules.finance_os.audit_explorer.services.audit_explorer_service import explore
from app.modules.finance_os.audit_explorer.engine.lineage_engine import get_entity_lineage

router = APIRouter(tags=["finance-os-audit"])


@router.get("/search", response_model=SearchResponse)
def audit_search(
    context=Depends(build_request_context),
    q: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    require_audit_read(context.user)
    items = search(
        context.org_id,
        q=q,
        object_type=object_type,
        actor_id=actor_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return SearchResponse(request_id=context.request_id, items=items, count=len(items), offset=offset, limit=limit)


@router.get("/explore/{object_type}/{object_id}", response_model=ExploreResponse)
def explore_object(object_type: str, object_id: str, context=Depends(build_request_context)) -> ExploreResponse:
    require_audit_read(context.user)
    result = explore(context.org_id, object_type=object_type, object_id=object_id, trace_id=context.request_id)
    return ExploreResponse(
        request_id=context.request_id,
        object_type=object_type,
        object_id=object_id,
        timeline=result.get("timeline") or [],
        evidence=result.get("evidence") or [],
        ai_decisions=result.get("ai_decisions") or [],
        lineage=result.get("lineage"),
    )


@router.get("/lineage/{object_type}/{object_id}")
def object_lineage(object_type: str, object_id: str, context=Depends(build_request_context)) -> dict:
    require_audit_read(context.user)
    return {
        "request_id": context.request_id,
        "object_type": object_type,
        "object_id": object_id,
        "lineage": get_entity_lineage(context.org_id, object_id, trace_id=context.request_id),
    }
