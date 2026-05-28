from __future__ import annotations

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class SMSProvider:
    """Placeholder for MSG91/Twilio — configure SMS_API_* later."""

    def send(self, *, to: str, body: str) -> DeliveryResult:
        if not settings.sms_api_url.strip():
            log_event("notification.sms.placeholder", to=to)
            return DeliveryResult(status="skipped", provider="sms", detail="api_not_configured")
        return DeliveryResult(status="skipped", provider="sms", detail="not_implemented")


sms_provider = SMSProvider()
