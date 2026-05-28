from __future__ import annotations

from typing import Any

from app.modules.workflows.services.realtime_hub import workflow_realtime_hub


class RealtimeNotificationService:
    """Action Center / toast feed via existing workflow realtime hub."""

    def push_toast(
        self,
        org_id: str,
        *,
        notification_type: str,
        priority: str,
        title: str,
        body: str,
        notification_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        event = {
            "event_type": f"notification.{notification_type}",
            "channel": "action_center",
            "priority": priority,
            "title": title,
            "body": body,
            "notification_id": notification_id,
            "toast": True,
            "metadata": metadata or {},
        }
        workflow_realtime_hub.publish(org_id, event)

    def push_from_notification(self, org_id: str, notification: dict) -> None:
        self.push_toast(
            org_id,
            notification_type=str(notification.get("notification_type", "alert")),
            priority=str(notification.get("priority", "medium")),
            title=str(notification.get("subject") or notification.get("notification_type", "Alert")),
            body=str(notification.get("body", "")),
            notification_id=str(notification.get("id", "")),
            metadata={
                "related_entity_type": notification.get("related_entity_type"),
                "related_entity_id": notification.get("related_entity_id"),
            },
        )


realtime_notification_service = RealtimeNotificationService()
