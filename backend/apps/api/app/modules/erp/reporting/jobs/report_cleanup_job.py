from __future__ import annotations

from app.modules.erp.reporting.repositories.report_runs_repository import report_runs_repository
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository


def run_cleanup(org_id: str, *, days: int = 90) -> dict:
    if not reporting_schema_repository.schema_ready():
        return {"deleted": 0}
    deleted = report_runs_repository.delete_older_than(org_id, days=days)
    return {"deleted": deleted}
