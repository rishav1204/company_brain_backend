from __future__ import annotations

from typing import Any


def emit_notification_delivered(org_id: str, *, notification_id: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="notification.delivered",
            org_id=org_id,
            source="notifications.engine",
            entity_type="notification",
            entity_id=notification_id,
            payload={"notification_id": notification_id},
        )
    except Exception:
        return None


def emit_notification_failed(org_id: str, *, notification_id: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="notification.failed",
            org_id=org_id,
            source="notifications.engine",
            entity_type="notification",
            entity_id=notification_id,
            payload={"notification_id": notification_id},
        )
    except Exception:
        return None
