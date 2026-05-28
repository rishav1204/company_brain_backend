from __future__ import annotations

from typing import Any


def emit_notification_sent(org_id: str, *, notification_id: str, channel: str) -> dict[str, Any] | None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        return platform_event_service.publish(
            event_type="notification.sent",
            org_id=org_id,
            source="notifications.engine",
            entity_type="notification",
            entity_id=notification_id,
            payload={"notification_id": notification_id, "channel": channel},
        )
    except Exception:
        return None
