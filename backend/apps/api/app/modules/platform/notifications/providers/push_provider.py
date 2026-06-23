from __future__ import annotations

import httpx

from app.core.config import settings
from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.logger import log_event


class PushProvider:
    """FCM/APNs-compatible push gateway via configured PUSH_API_URL."""

    def send(self, *, user_id: str, title: str, body: str, data: dict | None = None) -> DeliveryResult:
        if not settings.push_api_url.strip():
            log_event("notification.push.skipped", user_id=user_id, title=title, reason="api_not_configured")
            return DeliveryResult(status="skipped", provider="push", detail="api_not_configured")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.push_api_token.strip():
            headers["Authorization"] = f"Bearer {settings.push_api_token.strip()}"
        payload = {"user_id": user_id, "title": title, "body": body, "data": data or {}}
        try:
            response = httpx.post(
                settings.push_api_url,
                headers=headers,
                json=payload,
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return DeliveryResult(status="completed", provider="push", response={"status_code": response.status_code})
            detail = f"http_{response.status_code}"
            log_event("notification.push.error", user_id=user_id, detail=detail)
            return DeliveryResult(status="error", provider="push", detail=detail)
        except Exception as exc:
            log_event("notification.push.error", user_id=user_id, detail=str(exc))
            return DeliveryResult(status="error", provider="push", detail=str(exc))


push_provider = PushProvider()
