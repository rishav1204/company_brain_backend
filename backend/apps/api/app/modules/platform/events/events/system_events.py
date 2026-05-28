from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_job_failed(org_id: str, *, queue: str, event_id: str, error: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="job.failed",
        org_id=org_id,
        source="platform.queue",
        payload={"queue": queue, "event_id": event_id, "error": error},
        trace_id=trace_id,
    )


def emit_retry_exceeded(org_id: str, *, queue: str, event_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="retry.exceeded",
        org_id=org_id,
        source="platform.queue",
        payload={"queue": queue, "event_id": event_id},
        trace_id=trace_id,
    )


def emit_queue_blocked(org_id: str, *, queue: str, reason: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="queue.blocked",
        org_id=org_id,
        source="platform.queue",
        payload={"queue": queue, "reason": reason},
        trace_id=trace_id,
    )
