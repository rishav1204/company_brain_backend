from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.services.realtime_hub import workflow_realtime_hub

router = APIRouter(prefix="/workflows/events", tags=["workflow-realtime"])


@router.get("/stream")
def workflow_event_stream(
    context=Depends(require_workflow_permission("workflow.read")),
    cursor: int = Query(default=0, ge=0),
):
    events, next_cursor = workflow_realtime_hub.since(context.org_id, cursor)
    payload = {"request_id": context.request_id, "events": events, "next_cursor": next_cursor}
    return payload


@router.get("/stream/sse")
def workflow_sse(context=Depends(require_workflow_permission("workflow.read"))):
    def generate():
        cursor = 0
        while True:
            events, cursor = workflow_realtime_hub.since(context.org_id, cursor)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            import time

            time.sleep(2)

    return StreamingResponse(generate(), media_type="text/event-stream")
