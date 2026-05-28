from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.platform.events.bus.event_registry import ALL_EVENTS, get_event_definition
from app.modules.platform.events.queues.dead_letter_queue import list_dlq_depth, requeue_from_dlq
from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.repositories.queue_repository import queue_repository
from app.modules.platform.events.schemas.event_schema import PublishEventRequest, ReplayEventsRequest
from app.modules.platform.events.services.event_service import platform_event_service
from app.services.event_topology import queue_groups

router = APIRouter(tags=["platform-events"])


@router.post("/events/publish")
def publish_event(request: PublishEventRequest, context=Depends(build_request_context)) -> dict:
    if request.org_id != context.org_id:
        raise HTTPException(status_code=403, detail="org_id mismatch")
    try:
        result = platform_event_service.publish(
            event_type=request.event_type,
            org_id=context.org_id,
            source=request.source,
            payload=request.payload,
            trace_id=request.trace_id or context.request_id,
            actor_id=request.actor_id or context.user_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            metadata=request.metadata,
            idempotency_key=request.idempotency_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        **result,
        "verification_status": "event_published",
    }


@router.get("/events/catalog")
def event_catalog(context=Depends(build_request_context)) -> dict:
    items = [
        {
            "event_type": d.event_type,
            "owner": d.owner,
            "category": d.category,
            "version": d.version,
        }
        for d in ALL_EVENTS.values()
    ]
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/events/registry/{event_type}")
def event_registry_lookup(event_type: str, context=Depends(build_request_context)) -> dict:
    definition = get_event_definition(event_type)
    if not definition:
        raise HTTPException(status_code=404, detail="Event type not in registry")
    return {
        "request_id": context.request_id,
        "event_type": definition.event_type,
        "owner": definition.owner,
        "category": definition.category,
    }


@router.post("/events/replay")
def replay_events(request: ReplayEventsRequest, context=Depends(build_request_context)) -> dict:
    replayed = platform_event_service.replay(
        context.org_id,
        event_type=request.event_type,
        limit=request.limit,
        actor_id=context.user_id,
        trace_id=context.trace_id or context.request_id,
    )
    return {
        "request_id": context.request_id,
        "replayed_count": len(replayed),
        "verification_status": "events_replayed",
    }


@router.get("/queues")
def list_queues(context=Depends(build_request_context)) -> dict:
    groups = queue_groups()
    lag = {name: queue_manager.lag(q) for name, q in groups.items()}
    dlq = {name: list_dlq_depth(q) for name, q in groups.items()}
    return {
        "request_id": context.request_id,
        "queues": groups,
        "lag": lag,
        "dlq_depth": dlq,
        "backend": "redis_streams",
    }


@router.post("/queues/{queue_name}/dlq/requeue")
def requeue_dlq(queue_name: str, limit: int = 10, context=Depends(build_request_context)) -> dict:
    groups = queue_groups()
    if queue_name not in groups.values():
        raise HTTPException(status_code=404, detail="Unknown queue")
    requeued = requeue_from_dlq(queue_name, limit=limit)
    return {"request_id": context.request_id, "requeued_count": len(requeued)}


@router.get("/jobs")
def list_jobs(queue: str | None = None, status: str | None = None, limit: int = 50, context=Depends(build_request_context)) -> dict:
    try:
        items = queue_repository.list_jobs(context.org_id, queue_name=queue, status=status, limit=limit)
    except Exception:
        items = []
    return {"request_id": context.request_id, "items": items, "verification_status": "jobs_listed"}
