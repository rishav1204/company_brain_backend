from fastapi import APIRouter, Depends, Query

from app.modules.platform.governance.api.deps import require_auditor_read
from app.modules.platform.governance.services.forensics_service import forensics_service
from app.modules.platform.governance.services.retention_service import retention_service
from app.services.metrics import metrics_store

router = APIRouter(tags=["governance-forensics"])


@router.get("/governance/forensics/timeline")
def forensics_timeline(
    context=Depends(require_auditor_read),
    trace_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=200, le=500),
) -> dict:
    return {
        "request_id": context.request_id,
        **forensics_service.incident_timeline(
            context.org_id,
            trace_id=trace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        ),
    }


@router.get("/governance/forensics/rollback/{entity_type}/{entity_id}")
def forensics_rollback(entity_type: str, entity_id: str, context=Depends(require_auditor_read)) -> dict:
    return {
        "request_id": context.request_id,
        **forensics_service.rollback_analysis(context.org_id, entity_type=entity_type, entity_id=entity_id),
    }


@router.get("/governance/metrics")
def governance_metrics(context=Depends(require_auditor_read)) -> dict:
    snap = metrics_store.snapshot()
    avg_approval_wait = 0
    if snap.approval_wait_samples:
        avg_approval_wait = snap.approval_wait_ms_total // snap.approval_wait_samples
    return {
        "request_id": context.request_id,
        "governance_audits": snap.governance_audits,
        "governance_violations": snap.governance_violations,
        "governance_compliance_alerts": snap.governance_compliance_alerts,
        "governance_webhook_deliveries": snap.governance_webhook_deliveries,
        "governance_replay_ops": snap.governance_replay_ops,
        "workflow_approvals": snap.workflow_approvals,
        "workflow_sla_breaches": snap.workflow_sla_breaches,
        "approval_wait_avg_ms": avg_approval_wait,
        "queue_retries": snap.queue_retries,
        "queue_dlq_count": snap.queue_dlq_count,
    }


@router.post("/governance/retention/archival/run")
def run_retention_archival(context=Depends(require_auditor_read)) -> dict:
    return {"request_id": context.request_id, **retention_service.schedule_archival(context.org_id)}
