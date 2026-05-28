from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.modules.workflows.repositories import approval_repo, workflow_repo
from app.modules.workflows.services.approval_service import approval_service
from app.modules.workflows.services.workflow_service import workflow_service


def run_timeout_checks(org_id: str, *, stale_hours: int = 72) -> dict:
    if not workflow_service.schema_ready():
        return {"timed_out": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    count = 0
    for inst in workflow_repo.list_instances(org_id, status="waiting_approval", limit=500):
        started = inst.get("started_at")
        if started and started > cutoff:
            continue
        pending = approval_repo.list_pending(org_id, limit=50)
        for row in pending:
            if row.get("workflow_instance_id") != inst["id"]:
                continue
            try:
                approval_service._expire(org_id, row, inst)
                count += 1
            except Exception:
                continue
    return {"org_id": org_id, "timed_out": count}
