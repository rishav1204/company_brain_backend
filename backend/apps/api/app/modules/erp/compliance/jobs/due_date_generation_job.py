from app.modules.erp.compliance.services.compliance_scheduler_service import compliance_scheduler_service


def run_due_date_generation(org_id: str) -> dict:
    return compliance_scheduler_service.run_daily(org_id)
