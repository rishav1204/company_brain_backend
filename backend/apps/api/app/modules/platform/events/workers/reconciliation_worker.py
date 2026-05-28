from __future__ import annotations

from app.services.logger import log_event


def process_reconciliation_event(org_id: str, envelope: dict) -> dict:
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    log_event("platform.reconciliation.daily", org_id=org_id, job=payload.get("job"))
    from app.modules.workflows.services.scheduled_workflow_service import scheduled_workflow_service

    started = scheduled_workflow_service.run_due(org_id, trace_id=str(envelope.get("trace_id", "")))
    return {"status": "completed", "started_count": len(started)}
