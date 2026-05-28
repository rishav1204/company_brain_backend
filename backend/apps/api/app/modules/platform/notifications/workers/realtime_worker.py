from __future__ import annotations

from app.modules.platform.notifications.services.realtime_service import realtime_notification_service


def process_realtime_notification(org_id: str, notification: dict) -> dict:
    realtime_notification_service.push_from_notification(org_id, notification)
    return {"status": "pushed"}
