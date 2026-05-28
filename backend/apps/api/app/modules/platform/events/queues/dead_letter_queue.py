from __future__ import annotations

from app.modules.platform.events.queues.queue_manager import queue_manager
from app.services.event_topology import queue_dlq_name


def list_dlq_depth(queue: str) -> int:
    return queue_manager.dlq_lag(queue)


def requeue_from_dlq(queue: str, *, limit: int = 10) -> list[dict]:
    """Requeue messages from DLQ back to primary queue (admin recovery)."""
    dlq = queue_dlq_name(queue)
    requeued: list[dict] = []
    for _ in range(limit):
        result = queue_manager.process_next(dlq)
        if result.status != "processed" or not result.envelope:
            break
        queue_manager.publish(result.envelope)
        requeued.append(result.envelope)
    return requeued
