from __future__ import annotations


def emit_posting_completed(org_id: str, journal_id: str, *, batch_id: str, latency_ms: int) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        payload = {"journal_id": journal_id, "batch_id": batch_id, "latency_ms": latency_ms}
        platform_event_service.publish(
            event_type="erp.journal.posting.completed",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload,
        )
    except Exception:
        pass
