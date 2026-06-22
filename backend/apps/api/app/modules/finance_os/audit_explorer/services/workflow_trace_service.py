from __future__ import annotations

from app.modules.finance_os.audit_explorer.read_models import workflow_read_models


def get_approval_chain(org_id: str, workflow_id: str) -> dict:
    instance = workflow_read_models.get_workflow_instance(org_id, workflow_id)
    approvals = workflow_read_models.list_approvals(org_id, workflow_id)
    steps = workflow_read_models.list_workflow_steps(org_id, workflow_id)
    intelligence: dict = {}
    try:
        from app.modules.finance_os.workflow_intelligence.services.workflow_pattern_service import workflow_pattern_service

        wf_type = (instance or {}).get("workflow_type") or "GENERIC"
        intelligence = workflow_pattern_service.analytics(org_id, workflow_type=str(wf_type))
    except Exception:
        intelligence = {}
    return {
        "workflow_id": workflow_id,
        "instance": instance,
        "approvals": approvals,
        "steps": steps,
        "intelligence": intelligence,
    }
