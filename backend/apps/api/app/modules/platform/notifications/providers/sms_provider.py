from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class SMSProvider:
    """MSG91/Twilio-compatible SMS gateway via configured SMS_API_URL."""

    def send(self, *, to: str, body: str) -> DeliveryResult:
        if not settings.sms_api_url.strip():
            log_event("notification.sms.skipped", to=to, reason="api_not_configured")
            return DeliveryResult(status="skipped", provider="sms", detail="api_not_configured")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.sms_api_token.strip():
            headers["Authorization"] = f"Bearer {settings.sms_api_token.strip()}"
        try:
            response = httpx.post(
                settings.sms_api_url,
                headers=headers,
                json={"to": to, "body": body},
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return DeliveryResult(status="completed", provider="sms", response={"status_code": response.status_code})
            detail = f"http_{response.status_code}"
            log_event("notification.sms.error", to=to, detail=detail)
            return DeliveryResult(status="error", provider="sms", detail=detail)
        except Exception as exc:
            log_event("notification.sms.error", to=to, detail=str(exc))
            return DeliveryResult(status="error", provider="sms", detail=str(exc))


sms_provider = SMSProvider()
