from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.platform.api_gateway.services.event_stream_service import event_stream_service

router = APIRouter()


@router.get("/events/catalog")
def event_catalog(context=Depends(build_request_context)) -> dict:
    items = event_stream_service.list_partner_catalog()
    return {"request_id": context.request_id, "items": items}


@router.get("/events")
def list_events(
    context=Depends(build_request_context),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> dict:
    items = event_stream_service.list_events(context.org_id, event_type=event_type, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/events/{event_id}")
def get_event(event_id: str, context=Depends(build_request_context)) -> dict:
    item = event_stream_service.get_event(context.org_id, event_id)
    return {"request_id": context.request_id, "item": item}
