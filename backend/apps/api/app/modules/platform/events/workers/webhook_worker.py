from __future__ import annotations

from app.modules.platform.events.services.webhook_service import webhook_service
from app.modules.platform.integrations.services.webhook_service import integrations_webhook_service
from app.services.logger import log_event


def process_integration_event(envelope: dict) -> dict:
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    if event_type == "integration.ingestion.received":
        try:
            from app.modules.platform.integrations.workers.ingestion_worker import process_ingestion_job

            return process_ingestion_job(envelope)
        except Exception:
            return {"status": "error"}
    if event_type == "webhook.received":
        # Process both legacy platform webhooks and Module 7 integrations webhooks.
        webhook_service.process_pending_deliveries(org_id)
        try:
            integrations_webhook_service.process_pending_deliveries(org_id)
        except Exception:
            pass
        return {"status": "processed"}
    log_event("platform.integration.event", org_id=org_id, consumed_event_type=event_type)
    return {"status": "acknowledged"}
