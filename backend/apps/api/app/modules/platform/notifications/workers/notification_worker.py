from __future__ import annotations

from uuid import uuid4

from app.core.config import settings
from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.events.services.retry_service import schedule_retry
from app.modules.platform.notifications.repositories.notification_repository import notification_repository
from app.modules.platform.notifications.services.notification_service import notification_service


def process_notification_event(envelope: dict, *, queue: str | None = None, claim_token: str | None = None) -> dict:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    trace_id = str(envelope.get("trace_id") or "") or None

    if event_type == "notification.deliver":
        payload = envelope.get("payload") or {}
        nid = str(payload.get("notification_id", ""))
        channel = str(payload.get("channel", "email"))
        if not nid:
            return {"status": "skipped"}
        notification = notification_repository.get(org_id, nid) if notification_repository.schema_ready() else None
        if not notification:
            notification = {
                "id": nid,
                "channel": channel,
                "body": payload.get("body", ""),
                "subject": payload.get("subject"),
                "recipient_address": payload.get("recipient_address"),
                "recipient_user_id": payload.get("recipient_user_id"),
                "notification_type": payload.get("notification_type", "alert"),
            }
        notification["channel"] = channel
        notification["_attempts"] = int(payload.get("_attempts", envelope.get("_attempts", 0)))
        result = notification_service.process_notification_record(org_id, notification, trace_id=trace_id)
        if result.get("status") == "retry":
            _requeue_delivery(org_id, notification, envelope, attempt=int(result.get("attempt", 1)))
        elif result.get("status") in {"failed", "dlq"} and queue:
            queue_manager.fail_claim(queue, envelope, claim_token, str(result.get("detail", "delivery_failed")))
        return result

    created = notification_service.handle_event_envelope(envelope)
    return {"status": "processed", "count": len(created)}


def _requeue_delivery(org_id: str, notification: dict, envelope: dict, *, attempt: int) -> None:
    retry_envelope = schedule_retry(
        {
            **envelope,
            "event_id": str(uuid4()),
            "event_type": "notification.deliver",
            "org_id": org_id,
            "source": "notifications.retry",
            "payload": {
                "notification_id": notification.get("id"),
                "channel": notification.get("channel"),
                "_attempts": attempt,
            },
        }
    )
    queue_manager.publish(retry_envelope)
