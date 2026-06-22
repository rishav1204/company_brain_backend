from __future__ import annotations

from app.modules.platform.api_gateway.schemas.scope_catalog import normalize_event_type


def dispatch_event(org_id: str, event_type: str, envelope: dict) -> list[dict]:
    """Canonical outbound webhook path — integrations stack only (M36)."""
    from app.core.config import settings
    from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service

    if getattr(settings, "webhook_dispatch_legacy", False):
        try:
            from app.modules.platform.events.services.webhook_service import webhook_service

            webhook_service.dispatch_event(org_id, event_type, envelope)
        except Exception:
            pass

    canonical = normalize_event_type(event_type)
    return integrations_webhook_service.dispatch_event(org_id, canonical, envelope)
