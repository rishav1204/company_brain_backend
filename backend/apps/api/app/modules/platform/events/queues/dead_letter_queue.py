from __future__ import annotations

from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.middleware.event_validation_middleware import validate_incoming_event
from app.services.event_topology import queue_dlq_name
from app.services.logger import log_event


def list_dlq_depth(queue: str) -> int:
    return queue_manager.dlq_lag(queue)


def requeue_from_dlq(queue: str, *, limit: int = 10) -> list[dict]:
    """
    RQ-04: Safe DLQ replay.
    - Validate envelope before replay
    - Preserve original event_id/trace_id/metadata
    - Prevent replay loops by marking replay metadata
    """
    dlq = queue_dlq_name(queue)
    requeued: list[dict] = []
    for _ in range(limit):
        result = queue_manager.process_next(dlq)
        if result.status != "processed" or not result.envelope:
            break
        env = dict(result.envelope)
        try:
            org_id = str(env.get("org_id") or "").strip()
            if not org_id:
                raise ValueError("missing org_id")
            validate_incoming_event(env, org_id=org_id)
            meta = env.get("metadata") if isinstance(env.get("metadata"), dict) else {}
            replay_count = int(meta.get("dlq_replay_count") or 0) + 1
            meta["dlq_replay_count"] = replay_count
            meta["dlq_replayed_from"] = dlq
            env["metadata"] = meta
            if replay_count > 5:
                log_event("dlq.replay_blocked", org_id=org_id, queue=queue, event_id=str(env.get("event_id")), reason="replay_limit")
                continue
            queue_manager.publish(env)
            requeued.append(env)
        except Exception as exc:
            log_event("dlq.replay_invalid_envelope", queue=queue, error=str(exc))
    return requeued
