"""Archival-only scheduler — audit data is never hard-deleted."""

from app.modules.platform.governance.retention.archival_jobs import run_archival_job


def schedule_purge_checks(org_id: str) -> dict:
    return {"status": "archival_only", "detail": "hard_delete_disabled", "job": run_archival_job(org_id)}
