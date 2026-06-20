from __future__ import annotations


def workflow_context(org_id: str, workflow_id: str | None) -> dict:
    if not workflow_id:
        return {}
    try:
        from app.modules.finance_os.workflow_intelligence.services.workflow_insight_service import workflow_insight_service

        return workflow_insight_service.health(org_id)
    except Exception:
        return {"workflow_id": workflow_id}
