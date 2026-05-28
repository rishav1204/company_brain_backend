from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.repositories import escalation_repo
from app.modules.workflows.schemas.escalation_schema import EscalationListOut, EscalationOut
from app.modules.workflows.services.escalation_service import escalation_service
from app.modules.workflows.services.workflow_service import workflow_service

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=EscalationListOut)
def list_escalations(
    context=Depends(require_workflow_permission("workflow.read")),
    unresolved_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> EscalationListOut:
    if not workflow_service.schema_ready():
        return EscalationListOut(
            request_id=context.request_id,
            items=[],
            confidence=0.8,
            verification_status="schema_not_ready",
        )
    rows = escalation_repo.list_escalations(context.org_id, unresolved_only=unresolved_only, limit=limit + offset)
    rows = rows[offset : offset + limit]
    items = [
        EscalationOut(
            id=r["id"],
            workflow_instance_id=r["workflow_instance_id"],
            escalation_type=r["escalation_type"],
            escalated_to=r.get("escalated_to"),
            triggered_at=r["triggered_at"],
            workflow_type=r.get("workflow_type"),
        )
        for r in rows
    ]
    return EscalationListOut(
        request_id=context.request_id,
        items=items,
        confidence=0.95,
        verification_status="verified",
    )


@router.post("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: str,
    context=Depends(require_workflow_permission("workflow.write", mode="write")),
) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    ok = escalation_repo.resolve(context.org_id, escalation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Escalation not found")
    from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator

    esc_rows = escalation_repo.list_escalations(context.org_id, unresolved_only=False, limit=1)
    if esc_rows:
        inst_id = esc_rows[0].get("workflow_instance_id")
        if inst_id:
            workflow_orchestrator.run_from_step(org_id=context.org_id, instance_id=inst_id, trace_id=context.request_id)
    return {"request_id": context.request_id, "escalation_id": escalation_id, "verification_status": "resolved"}


@router.post("/run-sla-check")
def run_sla_check(context=Depends(require_workflow_permission("workflow.write", mode="write"))) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    breaches = escalation_service.process_sla_breaches(context.org_id, trace_id=context.request_id)
    reminders = escalation_service.process_reminders(context.org_id, trace_id=context.request_id)
    pending = escalation_service.process_pending_escalations(context.org_id, trace_id=context.request_id)
    return {
        "request_id": context.request_id,
        "breach_count": len(breaches),
        "reminder_count": reminders,
        "manager_escalations": len(pending),
        "verification_status": "sla_check_complete",
    }
