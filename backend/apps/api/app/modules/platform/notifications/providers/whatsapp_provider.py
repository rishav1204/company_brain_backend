from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class WhatsAppProvider:
    """Placeholder for Meta WhatsApp Business API — configure WHATSAPP_API_* later."""

    def send(self, *, to: str, template_key: str, variables: dict) -> DeliveryResult:
        if not settings.whatsapp_api_url.strip():
            log_event("notification.whatsapp.placeholder", to=to, template=template_key)
            return DeliveryResult(status="skipped", provider="whatsapp", detail="api_not_configured")
        try:
            response = httpx.post(
                settings.whatsapp_api_url,
                headers={"Authorization": f"Bearer {settings.whatsapp_api_token}"},
                json={"to": to, "template": template_key, "variables": variables},
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return DeliveryResult(status="completed", provider="whatsapp")
            return DeliveryResult(status="error", provider="whatsapp", detail=f"http_{response.status_code}")
        except Exception as exc:
            return DeliveryResult(status="error", provider="whatsapp", detail=str(exc))


whatsapp_provider = WhatsAppProvider()
