from app.modules.erp.compliance.services.escalation_service import escalation_service


def run_escalation_job(org_id: str) -> dict:
    return escalation_service.process_overdue(org_id)
