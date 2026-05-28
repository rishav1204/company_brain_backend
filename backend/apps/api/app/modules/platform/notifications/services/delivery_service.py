from __future__ import annotations

from app.core.config import settings
from app.modules.platform.notifications.providers.email_provider import email_provider
from app.modules.platform.notifications.providers.push_provider import push_provider
from app.modules.platform.notifications.providers.slack_provider import slack_provider
from app.modules.platform.notifications.providers.sms_provider import sms_provider
from app.modules.platform.notifications.providers.teams_provider import teams_provider
from app.modules.platform.notifications.providers.whatsapp_provider import whatsapp_provider
from app.modules.platform.notifications.repositories.notification_repository import notification_repository
from app.modules.platform.notifications.services.retry_service import should_retry_notification


class DeliveryService:
    FALLBACK_ORDER = ("email", "whatsapp", "slack", "sms", "in_app")

    def deliver(self, org_id: str, notification: dict) -> dict:
        channel = str(notification.get("channel", "in_app"))
        nid = str(notification["id"])
        attempt = int(notification.get("_attempts", 0)) + 1
        result = self._send_channel(notification)

        if notification_repository.schema_ready():
            notification_repository.append_delivery_log(
                org_id,
                notification_id=nid,
                provider=result.provider,
                delivery_status=result.status,
                provider_response={"detail": result.detail, "response": result.response},
                attempt_count=attempt,
            )

        if result.status == "completed" or result.status == "skipped":
            notification_repository.update_status(org_id, nid, "sent", sent=True)
            return {"status": "sent", "provider": result.provider}

        if should_retry_notification(attempt):
            return {"status": "retry", "attempt": attempt, "detail": result.detail}

        notification_repository.update_status(org_id, nid, "failed")
        fallback = self._try_fallback(org_id, notification, channel)
        if fallback:
            return {"status": "fallback_sent", "detail": result.detail, "fallback": fallback}
        return {"status": "failed", "detail": result.detail, "dlq": True}

    def _send_channel(self, notification: dict):
        channel = notification.get("channel")
        body = str(notification.get("body", ""))
        subject = str(notification.get("subject") or "Finance OS")
        if channel == "email":
            to = notification.get("recipient_address")
            if not to:
                from app.modules.platform.notifications.providers.base_provider import DeliveryResult

                return DeliveryResult(status="error", provider="email", detail="no_recipient_email")
            return email_provider.send(to=to, subject=subject, body=body)
        if channel == "slack":
            return slack_provider.send(channel="#finance-ops", text=body)
        if channel == "teams":
            return teams_provider.send(text=body)
        if channel == "whatsapp":
            return whatsapp_provider.send(
                to=str(notification.get("recipient_address", "")),
                template_key=str(notification.get("notification_type", "alert")),
                variables=notification.get("metadata") or {},
            )
        if channel == "sms":
            return sms_provider.send(to=str(notification.get("recipient_address", "")), body=body)
        if channel == "push":
            return push_provider.send(
                user_id=str(notification.get("recipient_user_id", "")),
                title=subject,
                body=body,
            )
        from app.modules.platform.notifications.providers.base_provider import DeliveryResult

        return DeliveryResult(status="completed", provider="in_app")

    def _try_fallback(self, org_id: str, notification: dict, failed_channel: str) -> str | None:
        for ch in self.FALLBACK_ORDER:
            if ch == failed_channel or ch == "in_app":
                continue
            copy = {**notification, "channel": ch, "_attempts": 0}
            if ch in {"email", "whatsapp", "sms"} and not notification.get("recipient_address"):
                continue
            if ch == "whatsapp" and not settings.whatsapp_api_url.strip():
                continue
            result = self._send_channel(copy)
            if result.status in {"completed", "skipped"}:
                notification_repository.update_status(org_id, str(notification["id"]), "sent", sent=True)
                return ch
        return None


delivery_service = DeliveryService()
