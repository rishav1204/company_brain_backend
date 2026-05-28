from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.services.event_queue import event_queue
from app.services.event_topology import queue_dlq_name

router = APIRouter()


@router.get("/ops/queues")
def integrations_queue_status(context=Depends(build_request_context)) -> dict:
    # Minimal queue visibility for integrations-related flows.
    queues = {
        "webhooks": "webhook.received",  # event_type, not queue name; included for UI reference
    }
    # We don't have dedicated queues yet; use global queue lag endpoints elsewhere.
    return {"request_id": context.request_id, "queues": queues, "lag": {}, "dlq_lag": {}}

