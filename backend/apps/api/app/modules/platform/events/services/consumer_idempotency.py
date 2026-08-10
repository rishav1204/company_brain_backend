from __future__ import annotations

from app.modules.platform.events.services.idempotency_service import platform_idempotency_service


class ConsumerIdempotencyService:
    """Ensures each event_id is processed at most once per queue handler."""

    def already_processed(self, org_id: str, event_id: str, queue: str) -> bool:
        if not org_id or not event_id:
            return False
        scope = f"event_consume:{queue}"
        cached = platform_idempotency_service.get_cached(org_id, scope, event_id)
        return cached is not None

    def mark_processed(self, org_id: str, event_id: str, queue: str) -> None:
        if not org_id or not event_id:
            return
        scope = f"event_consume:{queue}"
        from app.core.config import settings

        financial = {
            settings.queue_workflow_execution,
            settings.queue_workflow_approvals,
            settings.queue_integration_bank,
            settings.queue_integration_gst,
        }
        ttl_days = int(settings.consumer_dedup_financial_ttl_days) if queue in financial else int(settings.consumer_dedup_ttl_days)
        platform_idempotency_service.store(
            org_id,
            scope,
            event_id,
            request_payload={"event_id": event_id, "queue": queue},
            response_payload={"status": "processed"},
            ttl_days=ttl_days,
        )


consumer_idempotency = ConsumerIdempotencyService()
