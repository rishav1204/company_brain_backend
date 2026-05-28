from __future__ import annotations

from app.modules.platform.notifications.providers.base_provider import DeliveryResult
from app.services.integration_service import integration_service


class SlackProvider:
    def send(self, *, channel: str, text: str) -> DeliveryResult:
        result = integration_service.send_slack(channel, text)
        return DeliveryResult(status=result.status, provider="slack", detail=result.detail)


slack_provider = SlackProvider()
