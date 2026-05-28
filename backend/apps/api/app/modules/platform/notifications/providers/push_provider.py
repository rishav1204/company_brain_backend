from __future__ import annotations

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class PushProvider:
    """Placeholder for FCM/APNs — configure PUSH_API_URL later."""

    def send(self, *, user_id: str, title: str, body: str, data: dict | None = None) -> DeliveryResult:
        if not settings.push_api_url.strip():
            log_event("notification.push.placeholder", user_id=user_id, title=title)
            return DeliveryResult(status="skipped", provider="push", detail="api_not_configured")
        return DeliveryResult(status="skipped", provider="push", detail="not_implemented")


push_provider = PushProvider()
