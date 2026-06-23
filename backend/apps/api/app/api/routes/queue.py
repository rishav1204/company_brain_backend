from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.modules.core.iam.middleware.permission_guard import require_permission
from app.services.event_topology import finance_topics, queue_groups, service_boundaries
from app.services.principal_context import principal_from_request_context
from app.services.redis_queue_service import redis_queue_service
from app.services.repositories import audit_repo

router = APIRouter(tags=["queue"])


class QueueEnqueueRequest(BaseModel):
    idempotency_key: str
    payload: dict


@router.post("/queue/enqueue")
def enqueue_message(request: QueueEnqueueRequest, context=Depends(require_permission("ops.queue.manage"))) -> dict:
    payload = dict(request.payload)
    payload.setdefault("org_id", context.org_id)
    payload.setdefault("trace_id", context.request_id)
    payload["principal"] = principal_from_request_context(context)
    result = redis_queue_service.enqueue(idempotency_key=request.idempotency_key, payload=payload)
    if result.status == "error":
        raise HTTPException(status_code=503, detail=f"Queue backend unavailable: {result.detail}")
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="queue.enqueue",
        object_ref="queue:main",
        payload_jsonb={"idempotency_key": request.idempotency_key, "result": result.status},
    )
    return {
        "request_id": context.request_id,
        "accepted": result.status == "queued",
        "result": result.status,
        "detail": result.detail,
        "confidence": 0.93 if result.status == "queued" else 0.7,
        "verification_status": "queued" if result.status == "queued" else "queue_error",
    }


@router.post("/queue/process-next")
def process_next(context=Depends(require_permission("ops.queue.manage"))) -> dict:
    result = redis_queue_service.process_next()
    if result.status == "error":
        raise HTTPException(status_code=503, detail=f"Queue processing failed: {result.detail}")
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="system",
        actor_id="queue-processor",
        event_type="queue.process_next",
        object_ref="queue:main",
        payload_jsonb={"result": result.status},
    )
    return {
        "request_id": context.request_id,
        "result": {
            "status": result.status,
            "detail": result.detail,
            "payload": result.payload,
        },
        "confidence": 0.92,
        "verification_status": "processed",
    }


@router.get("/queue/topology")
def queue_topology(context=Depends(build_request_context)) -> dict:
    topics = finance_topics()
    queues = queue_groups()
    return {
        "request_id": context.request_id,
        "queues": queues,
        "topics": topics,
        "service_boundaries": service_boundaries(),
        "dlq_suffix": ".dlq",
        "confidence": 0.95,
        "verification_status": "topology_declared",
    }
