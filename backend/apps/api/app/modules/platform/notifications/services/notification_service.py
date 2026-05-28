from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.platform.notifications.repositories.notification_repository import notification_repository
from app.modules.platform.notifications.repositories.preference_repository import preference_repository
from app.modules.platform.notifications.services.audit_bridge import audit_notification_delivery
from app.modules.platform.notifications.services.delivery_service import delivery_service
from app.modules.platform.notifications.services.event_router import (
    build_template_variables,
    extract_recipients,
    resolve_notification_plan,
)
from app.modules.platform.notifications.services.quiet_hours import in_quiet_hours
from app.modules.platform.notifications.services.realtime_service import realtime_notification_service
from app.modules.platform.notifications.services.recipient_resolver import enrich_recipients, resolve_user_contact
from app.modules.platform.notifications.services.template_service import template_service
from app.services.logger import log_event
from app.services.metrics import metrics_store
from app.services.trace import trace_span


class NotificationService:
    def schema_ready(self) -> bool:
        return notification_repository.schema_ready()

    def handle_event_envelope(self, envelope: dict) -> list[dict]:
        event_type = str(envelope.get("event_type", ""))
        org_id = str(envelope.get("org_id", ""))
        if not org_id or not event_type:
            return []
        plan = resolve_notification_plan(event_type)
        if not plan:
            return []
        notification_type, priority, channels = plan
        variables = build_template_variables(envelope)
        recipients = enrich_recipients(org_id, extract_recipients(envelope))
        if not recipients:
            recipients = [{"user_id": None, "email": None}]
        created: list[dict] = []
        for recipient in recipients:
            user_id = recipient.get("user_id")
            for channel in channels:
                if user_id and not self._channel_allowed(org_id, str(user_id), channel, notification_type):
                    continue
                row = self.dispatch(
                    org_id,
                    notification_type=notification_type,
                    channel=channel,
                    priority=priority,
                    variables={**variables, "recipient_name": recipient.get("display_name") or variables.get("recipient_name")},
                    recipient_user_id=user_id,
                    recipient_address=recipient.get("email"),
                    related_entity_type=envelope.get("entity_type"),
                    related_entity_id=str(envelope.get("entity_id") or "") or None,
                    event_type=event_type,
                    event_id=str(envelope.get("event_id") or envelope.get("id") or "") or None,
                    metadata=variables,
                    trace_id=str(envelope.get("trace_id") or "") or None,
                )
                if row:
                    created.append(row)
        return created

    def _channel_allowed(self, org_id: str, user_id: str, channel: str, notification_type: str) -> bool:
        if not preference_repository.is_enabled(org_id, user_id, channel, notification_type):
            return False
        prefs = preference_repository.get_preference(org_id, user_id, channel, notification_type)
        if prefs and in_quiet_hours(prefs.get("quiet_hours")):
            return channel == "in_app"
        return True

    def dispatch(
        self,
        org_id: str,
        *,
        notification_type: str,
        channel: str,
        priority: str = "medium",
        variables: dict | None = None,
        recipient_user_id: str | None = None,
        recipient_address: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        event_type: str | None = None,
        event_id: str | None = None,
        metadata: dict | None = None,
        trace_id: str | None = None,
    ) -> dict | None:
        if recipient_user_id and not recipient_address and channel in {"email", "whatsapp", "sms"}:
            contact = resolve_user_contact(org_id, recipient_user_id)
            recipient_address = contact.get("email")

        if not self.schema_ready():
            realtime_notification_service.push_toast(
                org_id,
                notification_type=notification_type,
                priority=priority,
                title=notification_type,
                body=str((variables or {}).get("body", "")),
            )
            return None

        if event_id and notification_repository.exists_for_event(
            org_id,
            event_id=event_id,
            channel=channel,
            notification_type=notification_type,
            recipient_user_id=recipient_user_id,
        ):
            return None

        with trace_span("notification.dispatch", channel=channel, notification_type=notification_type):
            subject, body = template_service.render(
                org_id, template_key=notification_type, channel=channel, variables=variables or {}
            )
            row = notification_repository.create(
                org_id,
                notification_type=notification_type,
                channel=channel,
                body=body,
                subject=subject,
                recipient_user_id=recipient_user_id,
                recipient_address=recipient_address,
                priority=priority,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                event_type=event_type,
                event_id=event_id,
                metadata=metadata,
            )
            full = {
                **row,
                "channel": channel,
                "body": body,
                "subject": subject,
                "notification_type": notification_type,
                "priority": priority,
                "recipient_address": recipient_address,
                "recipient_user_id": recipient_user_id,
                "metadata": metadata or {},
            }

            if channel == "in_app":
                realtime_notification_service.push_from_notification(org_id, {**full, "id": row.get("id")})
                notification_repository.update_status(org_id, row["id"], "sent", sent=True)
                metrics_store.incr_notification_sent()
                self._on_sent(org_id, row["id"], channel, trace_id=trace_id)
                self._emit_delivery_event(org_id, row["id"], "delivered")
                return full

            self._enqueue_channel_delivery(org_id, full)
            return full

    def process_notification_record(self, org_id: str, notification: dict, *, trace_id: str | None = None) -> dict:
        started = time.perf_counter()
        with trace_span("notification.deliver", channel=str(notification.get("channel"))):
            result = delivery_service.deliver(org_id, notification)
        latency_ms = int((time.perf_counter() - started) * 1000)
        metrics_store.record_notification_delivery_latency(latency_ms)
        nid = str(notification.get("id", ""))
        channel = str(notification.get("channel", ""))
        if result.get("status") in {"sent", "fallback_sent"}:
            metrics_store.incr_notification_sent()
            self._on_sent(org_id, nid, channel, trace_id=trace_id)
            self._emit_delivery_event(org_id, nid, "delivered")
            audit_notification_delivery(org_id, notification_id=nid, channel=channel, status="delivered", trace_id=trace_id)
        elif result.get("status") == "failed":
            metrics_store.incr_notification_failed()
            self._emit_delivery_event(org_id, nid, "failed")
            audit_notification_delivery(org_id, notification_id=nid, channel=channel, status="failed", trace_id=trace_id)
        elif result.get("status") == "dlq":
            metrics_store.incr_notification_failed()
            audit_notification_delivery(org_id, notification_id=nid, channel=channel, status="dlq", trace_id=trace_id)
        return result

    def _on_sent(self, org_id: str, notification_id: str, channel: str, *, trace_id: str | None) -> None:
        try:
            from app.modules.platform.notifications.events.notification_events import emit_notification_sent

            emit_notification_sent(org_id, notification_id=notification_id, channel=channel)
        except Exception:
            pass
        audit_notification_delivery(
            org_id, notification_id=notification_id, channel=channel, status="sent", trace_id=trace_id
        )

    def _enqueue_channel_delivery(self, org_id: str, notification: dict) -> None:
        channel = notification.get("channel", "email")
        queue_map = {
            "email": settings.queue_notifications_email,
            "whatsapp": settings.queue_notifications_whatsapp,
            "push": settings.queue_notifications_push,
            "slack": settings.queue_notifications_dispatch,
        }
        envelope = {
            "event_id": str(uuid4()),
            "event_type": "notification.deliver",
            "org_id": org_id,
            "source": "notifications.engine",
            "payload": {"notification_id": notification.get("id"), "channel": channel},
        }
        queue_manager.publish(envelope)

    def _emit_delivery_event(self, org_id: str, notification_id: str, status: str) -> None:
        try:
            from app.modules.platform.notifications.events.delivery_events import (
                emit_notification_delivered,
                emit_notification_failed,
            )

            if status == "delivered":
                emit_notification_delivered(org_id, notification_id=notification_id)
            else:
                emit_notification_failed(org_id, notification_id=notification_id)
        except Exception:
            pass

    def list_notifications(self, org_id: str, user_id: str, **filters: Any) -> list[dict]:
        return notification_repository.list_for_user(org_id, user_id=user_id, **filters)

    def acknowledge(self, org_id: str, notification_id: str) -> bool:
        return notification_repository.acknowledge(org_id, notification_id)

    def snooze(self, org_id: str, notification_id: str, *, until_iso: str) -> bool:
        return notification_repository.snooze(org_id, notification_id, until_iso=until_iso)

    def unread_count(self, org_id: str, user_id: str) -> int:
        return notification_repository.unread_count(org_id, user_id)


notification_service = NotificationService()
