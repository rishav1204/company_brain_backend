from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.modules.platform.notifications.services.notification_service import notification_service

router = APIRouter(tags=["notifications"])


class SnoozeBody(BaseModel):
    until: str


@router.get("/notifications")
def list_notifications(
    context=Depends(build_request_context),
    unread_only: bool = Query(default=False),
    notification_type: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> dict:
    items = notification_service.list_notifications(
        context.org_id,
        context.user_id,
        unread_only=unread_only,
        notification_type=notification_type,
        channel=channel,
        priority=priority,
        limit=limit,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/notifications/unread-count")
def unread_count(context=Depends(build_request_context)) -> dict:
    count = notification_service.unread_count(context.org_id, context.user_id)
    return {"request_id": context.request_id, "unread_count": count}


@router.post("/notifications/{notification_id}/acknowledge")
def acknowledge(notification_id: str, context=Depends(build_request_context)) -> dict:
    ok = notification_service.acknowledge(context.org_id, notification_id)
    return {"request_id": context.request_id, "acknowledged": ok}


@router.post("/notifications/{notification_id}/snooze")
def snooze(notification_id: str, body: SnoozeBody, context=Depends(build_request_context)) -> dict:
    ok = notification_service.snooze(context.org_id, notification_id, until_iso=body.until)
    return {"request_id": context.request_id, "snoozed": ok}
