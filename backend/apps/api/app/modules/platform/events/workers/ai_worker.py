from __future__ import annotations

from app.services.event_bus import event_bus
from app.services.logger import log_event


def process_ai_event(envelope: dict) -> dict:
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    if event_type in {"payment.risk.detected", "risk.detected"}:
        log_event("platform.ai.risk", org_id=org_id, payload=payload)
        return {"status": "completed"}
    if event_type in {"reconciliation.match.suggested", "invoice.ai.reviewed", "ai.reconciliation.suggested"}:
        log_event("platform.ai.reconciliation", org_id=org_id, payload=payload)
        if event_type == "ai.reconciliation.suggested":
            try:
                from app.modules.erp.treasury.ai.reconciliation_assistant import suggest_reconciliation_matches

                log_event(
                    "platform.ai.reconciliation.enrichment",
                    org_id=org_id,
                    entity_id=envelope.get("entity_id"),
                    summary=payload.get("summary"),
                )
            except Exception:
                pass
        return {"status": "completed"}
    if event_type == "agent.run.requested":
        event_bus.publish(
            event_type="agent.run.requested",
            org_id=org_id,
            source=str(envelope.get("source", "platform.ai_worker")),
            trace_id=str(envelope.get("trace_id", "")),
            payload=payload,
            principal=envelope.get("principal"),
        )
        return {"status": "forwarded"}
    log_event("platform.ai.generic", org_id=org_id, event_type=event_type)
    return {"status": "completed"}
