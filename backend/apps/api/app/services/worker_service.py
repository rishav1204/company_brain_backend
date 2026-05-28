from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.services.consumer_idempotency import consumer_idempotency
from app.modules.platform.events.services.event_service import platform_event_service
from app.services.event_consumers import consume_event
from app.services.event_topology import queue_groups
from app.services.logger import log_event
from app.services.redis_queue_service import redis_queue_service


def _process_queue(queue: str) -> dict:
    claim = queue_manager.claim_next(queue=queue)
    status = claim.status
    if status != "claimed" or not claim.envelope:
        return {"status": status, "detail": claim.detail}

    envelope = claim.envelope
    org_id = str(envelope.get("org_id", ""))
    event_id = str(envelope.get("event_id", ""))
    event_type = str(envelope.get("event_type", ""))

    if consumer_idempotency.already_processed(org_id, event_id, queue):
        queue_manager.complete_claim(queue, envelope, claim.claim_token)
        return {"status": "deduped", "detail": "consumer_idempotent"}

    try:
        from app.modules.platform.events.middleware.event_trace_middleware import trace_event_processing
        from app.modules.platform.events.middleware.event_validation_middleware import validate_incoming_event

        if org_id:
            validate_incoming_event(envelope, org_id=org_id)
        with trace_event_processing(event_type, queue):
            consume_event(queue=queue, envelope=envelope)
        consumer_idempotency.mark_processed(org_id, event_id, queue)
        queue_manager.complete_claim(queue, envelope, claim.claim_token)
        if org_id and event_id:
            platform_event_service.mark_processed(org_id, event_id)
        return {"status": "processed"}
    except Exception as exc:
        log_event("worker.consumer.error", queue=queue, error=str(exc), event_id=event_id)
        result = queue_manager.fail_claim(queue, envelope, claim.claim_token, str(exc))
        return {"status": result.status, "detail": result.detail}


def run_queue_worker_once() -> dict:
    result = redis_queue_service.process_next()
    log_event("worker.process_next", status=result.status, detail=result.detail)
    routed_results = {}
    for queue in queue_groups().values():
        try:
            routed_results[queue] = _process_queue(queue)
        except Exception as exc:
            routed_results[queue] = {"status": "error", "detail": str(exc)}
        log_event(
            "worker.event_queue.process_next",
            queue=queue,
            status=routed_results[queue].get("status"),
            detail=routed_results[queue].get("detail"),
        )
    return {
        "status": result.status,
        "detail": result.detail,
        "payload": result.payload,
        "routed_queue_results": routed_results,
    }


def run_queue_worker_batch(iterations: int = 10) -> dict:
    iterations = max(1, min(iterations, 500))
    processed = 0
    retries = 0
    dlq = 0
    empty = 0
    for _ in range(iterations):
        summary = run_queue_worker_once()
        routed = summary.get("routed_queue_results", {})
        statuses = [str(item.get("status", "")) for item in routed.values()]
        if "processed" in statuses:
            processed += 1
        if "retry" in statuses:
            retries += 1
        if "dlq" in statuses:
            dlq += 1
        if "empty" in statuses or "delayed" in statuses:
            empty += 1
    lag_snapshot = {queue: queue_manager.lag(queue) for queue in queue_groups().values()}
    dlq_snapshot = {queue: queue_manager.dlq_lag(queue) for queue in queue_groups().values()}
    return {
        "iterations": iterations,
        "processed_iterations": processed,
        "retry_iterations": retries,
        "dlq_iterations": dlq,
        "empty_iterations": empty,
        "lag_snapshot": lag_snapshot,
        "dlq_snapshot": dlq_snapshot,
    }
