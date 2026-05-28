from __future__ import annotations

from app.modules.workflows.services.escalation_service import escalation_service


def run_escalation_checks(org_id: str, *, trace_id: str | None = None) -> dict:
    pending = escalation_service.process_pending_escalations(org_id, hours=48, trace_id=trace_id)
    risk = escalation_service.process_risk_escalations(org_id, trace_id=trace_id)
    finance = escalation_service.process_finance_escalations(org_id, trace_id=trace_id)
    compliance = escalation_service.process_compliance_escalations(org_id, trace_id=trace_id)
    return {
        "org_id": org_id,
        "manager_escalations": len(pending),
        "risk_escalations": len(risk),
        "finance_escalations": len(finance),
        "compliance_escalations": len(compliance),
    }
