from __future__ import annotations

from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service


class WebhookService:
    def create_subscription(
        self,
        org_id: str,
        *,
        endpoint_url: str,
        event_types: list[str],
        name: str | None = None,
    ) -> tuple[dict, str]:
        item, secret = integrations_webhook_service.create_subscription(
            org_id, endpoint_url=endpoint_url, event_types=event_types
        )
        if name and item.get("id"):
            try:
                from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository

                webhook_repository.update_name(org_id, subscription_id=str(item["id"]), name=name)
            except Exception:
                pass
        return item, secret

    def list_subscriptions(self, org_id: str) -> list[dict]:
        return integrations_webhook_service.list_subscriptions(org_id)

    def deactivate(self, org_id: str, *, subscription_id: str) -> dict:
        from app.modules.platform.integrations.repositories.webhook_repository import webhook_repository

        return webhook_repository.deactivate(org_id, subscription_id=subscription_id)


webhook_service = WebhookService()
