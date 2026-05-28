from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class TeamsProvider:
    def send(self, *, text: str) -> DeliveryResult:
        if not settings.teams_webhook_url.strip():
            log_event("notification.teams.placeholder")
            return DeliveryResult(status="skipped", provider="teams", detail="webhook_not_configured")
        try:
            response = httpx.post(
                settings.teams_webhook_url,
                json={"text": text},
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return DeliveryResult(status="completed", provider="teams")
            return DeliveryResult(status="error", provider="teams", detail=f"http_{response.status_code}")
        except Exception as exc:
            return DeliveryResult(status="error", provider="teams", detail=str(exc))


teams_provider = TeamsProvider()
