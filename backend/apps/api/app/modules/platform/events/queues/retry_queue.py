from __future__ import annotations

from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.services.retry_service import schedule_retry


def requeue_with_backoff(envelope: dict, queue: str) -> dict:
    updated = schedule_retry(envelope)
    queue_manager.publish(updated)
    return updated
