from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.api.deps import build_request_context
from app.modules.platform.notifications.realtime.event_stream_dispatcher import event_stream_dispatcher
from app.modules.platform.notifications.services.subscription_service import subscription_service
from app.services.metrics import metrics_store
from pydantic import BaseModel

router = APIRouter(tags=["notification-realtime"])


class SubscribeBody(BaseModel):
    channel_key: str = "action_center"


@router.post("/realtime/subscribe")
def subscribe(body: SubscribeBody, context=Depends(build_request_context)) -> dict:
    row = subscription_service.subscribe(context.org_id, context.user_id, body.channel_key)
    return {"request_id": context.request_id, "subscription": row}


@router.get("/realtime/action-center")
def action_center_poll(
    context=Depends(build_request_context),
    cursor: int = Query(default=0, ge=0),
    channel: str | None = Query(default=None),
) -> dict:
    subscription_service.subscribe(context.org_id, context.user_id, channel or "action_center")
    metrics_store.incr_notification_realtime_connection()
    events, next_cursor = event_stream_dispatcher.since(context.org_id, cursor, channel=channel)
    toasts = [
        e
        for e in events
        if e.get("toast") or e.get("channel") == "action_center" or "notification." in str(e.get("event_type", ""))
    ]
    return {
        "request_id": context.request_id,
        "events": toasts,
        "next_cursor": next_cursor,
        "channel": channel or "action_center",
    }


@router.get("/realtime/action-center/sse")
async def action_center_sse(
    context=Depends(build_request_context),
    channel: str | None = Query(default=None),
) -> StreamingResponse:
    subscription_service.subscribe(context.org_id, context.user_id, channel or "action_center")
    metrics_store.incr_notification_realtime_connection()

    async def event_generator():
        cursor = 0
        while True:
            events, cursor = event_stream_dispatcher.since(context.org_id, cursor, channel=channel)
            for event in events:
                if event.get("toast") or "notification." in str(event.get("event_type", "")):
                    yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
