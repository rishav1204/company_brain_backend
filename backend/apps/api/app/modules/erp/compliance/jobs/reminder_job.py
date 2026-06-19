from app.modules.erp.compliance.services.reminder_service import reminder_service


def run_reminder_job(org_id: str) -> dict:
    return reminder_service.process_due(org_id)
