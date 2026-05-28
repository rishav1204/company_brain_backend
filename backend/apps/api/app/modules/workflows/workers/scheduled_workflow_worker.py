from __future__ import annotations

from app.modules.workflows.services.scheduled_workflow_service import scheduled_workflow_service


def run_scheduled_workflows(org_id: str, *, trace_id: str | None = None) -> dict:
    started = scheduled_workflow_service.run_due(org_id, trace_id=trace_id)
    return {"org_id": org_id, "started_count": len(started), "instance_ids": [s.get("id") for s in started]}
