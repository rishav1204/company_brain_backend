from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.integration_service import integration_service
from app.services.logger import log_event


class EmailProvider:
    """Resend free tier (3000/mo) primary; SMTP fallback; console in dev."""

    def send(self, *, to: str, subject: str, body: str) -> DeliveryResult:
        if settings.resend_api_key.strip():
            return self._send_resend(to=to, subject=subject, body=body)
        if settings.smtp_host and settings.smtp_from_email:
            result = integration_service.send_email(to, subject, body)
            return DeliveryResult(
                status=result.status,
                provider="smtp",
                detail=result.detail,
            )
        log_event("notification.email.dev", to=to, subject=subject)
        return DeliveryResult(status="completed", provider="console", detail="logged_dev_mode")

    def _send_resend(self, *, to: str, subject: str, body: str) -> DeliveryResult:
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": body.replace("\n", "<br>"),
                    "text": body,
                },
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return DeliveryResult(status="completed", provider="resend", response=response.json())
            return DeliveryResult(status="error", provider="resend", detail=f"http_{response.status_code}")
        except Exception as exc:
            return DeliveryResult(status="error", provider="resend", detail=str(exc))


email_provider = EmailProvider()
