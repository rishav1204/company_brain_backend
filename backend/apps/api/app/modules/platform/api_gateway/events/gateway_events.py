from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


class GatewayEvents:
    def emit_key_created(self, org_id: str, *, api_key_id: str) -> None:
        platform_event_service.publish(
            event_type="api.key.created",
            org_id=org_id,
            source="api_gateway",
            payload={"api_key_id": api_key_id},
            entity_type="api_key",
            entity_id=api_key_id,
        )

    def emit_key_revoked(self, org_id: str, *, api_key_id: str) -> None:
        platform_event_service.publish(
            event_type="api.key.revoked",
            org_id=org_id,
            source="api_gateway",
            payload={"api_key_id": api_key_id},
            entity_type="api_key",
            entity_id=api_key_id,
        )

    def emit_webhook_delivered(self, org_id: str, *, delivery_id: str, event_type: str) -> None:
        platform_event_service.publish(
            event_type="webhook.delivered",
            org_id=org_id,
            source="api_gateway",
            payload={"delivery_id": delivery_id, "event_type": event_type},
            entity_type="webhook_delivery",
            entity_id=delivery_id,
        )

    def emit_webhook_failed(self, org_id: str, *, delivery_id: str, error: str) -> None:
        platform_event_service.publish(
            event_type="webhook.failed",
            org_id=org_id,
            source="api_gateway",
            payload={"delivery_id": delivery_id, "error": error},
            entity_type="webhook_delivery",
            entity_id=delivery_id,
        )

    def emit_integration_connected(self, org_id: str, *, connector_id: str, provider: str) -> None:
        platform_event_service.publish(
            event_type="integration.connected",
            org_id=org_id,
            source="api_gateway",
            payload={"connector_id": connector_id, "provider": provider},
            entity_type="connector",
            entity_id=connector_id,
        )


gateway_events = GatewayEvents()
