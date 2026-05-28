from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.core.config import settings
from app.services.event_queue import event_queue
from app.services.event_topology import queue_dlq_name

router = APIRouter(tags=["documents-pipeline"])


@router.get("/documents/pipeline/status")
def documents_pipeline_status(context=Depends(build_request_context)) -> dict:
    queues = {
        "ai_ocr": settings.queue_ai_ocr,
        "processing_extract": settings.queue_processing_extract,
        "processing_embed": settings.queue_processing_embed,
    }
    lag = {k: event_queue.lag(v) for k, v in queues.items()}
    dlq = {k: event_queue.lag(queue_dlq_name(v)) for k, v in queues.items()}
    return {"request_id": context.request_id, "queues": queues, "lag": lag, "dlq_lag": dlq}

