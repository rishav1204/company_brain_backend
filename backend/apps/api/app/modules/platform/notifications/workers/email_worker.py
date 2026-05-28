from __future__ import annotations

from app.modules.platform.notifications.services.notification_service import notification_service
from app.modules.platform.notifications.repositories.notification_repository import notification_repository


def process_email_notification(envelope: dict) -> dict:
    org_id = str(envelope.get("org_id", ""))
    payload = envelope.get("payload") or {}
    nid = str(payload.get("notification_id", ""))
    if not nid or not notification_repository.schema_ready():
        return {"status": "skipped"}
    notification = notification_repository.get(org_id, nid)
    if not notification:
        notification = {"id": nid, "channel": "email", "body": payload.get("body", ""), "subject": payload.get("subject")}
    notification["channel"] = "email"
    return notification_service.process_notification_record(org_id, notification)
