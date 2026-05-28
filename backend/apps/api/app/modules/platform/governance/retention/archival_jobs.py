from app.modules.platform.governance.services.retention_service import retention_service


def run_archival_job(org_id: str) -> dict:
    return retention_service.schedule_archival(org_id)
