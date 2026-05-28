from __future__ import annotations

from app.modules.workflows.services.escalation_service import escalation_service


def run_sla_checks(org_id: str, *, trace_id: str | None = None) -> dict:
    breaches = escalation_service.process_sla_breaches(org_id, trace_id=trace_id)
    reminders = escalation_service.process_reminders(org_id, trace_id=trace_id)
    return {"org_id": org_id, "breach_count": len(breaches), "reminder_count": reminders}
