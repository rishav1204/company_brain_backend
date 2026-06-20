from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.schemas.workflow_schema import (
    WorkflowDefinitionOut,
    WorkflowDetailOut,
    WorkflowInstanceOut,
    WorkflowStartRequest,
    WorkflowStepOut,
    WorkflowTransitionRequest,
)
from app.modules.workflows.engine.workflow_state_machine import status_to_legacy_state
from app.modules.workflows.repositories import step_repo, workflow_repo
from app.modules.workflows.services.workflow_service import workflow_service
from app.modules.workflows.validators.workflow_validator import validate_start_request, validate_transition_request
router = APIRouter(prefix="/workflows", tags=["workflows-v2"])


def _instance_out(row: dict) -> WorkflowInstanceOut:
    status = row.get("status") or row.get("state") or "running"
    legacy_state = status_to_legacy_state(status) if "status" in row else status
    return WorkflowInstanceOut(
        id=row.get("legacy_workflow_id") or row["id"],
        workflow_type=row["workflow_type"],
        status=status if "status" in row else legacy_state_to_status_compat(status),
        state=legacy_state,
        owner_user_id=row.get("started_by") or row.get("owner_user_id"),
        started_at=row["started_at"],
        completed_at=row.get("completed_at") or row.get("closed_at"),
        closed_at=row.get("completed_at") or row.get("closed_at"),
        priority=row.get("priority") or "normal",
        metadata=row.get("metadata") or {},
        legacy_workflow_id=row.get("legacy_workflow_id"),
    )


def legacy_state_to_status_compat(state: str) -> str:
    from app.modules.workflows.engine.workflow_state_machine import legacy_state_to_status

    return legacy_state_to_status(state)


@router.post("/start")
def start_workflow(
    request: WorkflowStartRequest,
    context=Depends(require_workflow_permission("workflow.write", mode="write")),
) -> dict:
    try:
        validate_start_request(workflow_key=request.workflow_key, workflow_type=request.workflow_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    metadata = dict(request.metadata or {})
    if request.amount is not None:
        metadata["amount"] = request.amount
    try:
        instance = workflow_service.start_workflow(
            org_id=context.org_id,
            user_id=context.user_id,
            workflow_key=request.workflow_key,
            workflow_type=request.workflow_type,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            metadata=metadata,
            trace_id=context.request_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "workflow_instance_id": instance.get("id"),
        "status": instance.get("status"),
        "confidence": 0.95,
        "verification_status": "workflow_started",
    }


@router.get("/definitions")
def list_definitions(context=Depends(require_workflow_permission("workflow.read"))) -> dict:
    if not workflow_service.schema_ready():
        return {"request_id": context.request_id, "items": [], "verification_status": "schema_not_ready"}
    rows = workflow_repo.list_definitions(context.org_id)
    items = [WorkflowDefinitionOut(**row) for row in rows]
    return {"request_id": context.request_id, "items": items, "confidence": 0.99, "verification_status": "verified"}


@router.get("/metrics/summary")
def workflow_metrics(context=Depends(require_workflow_permission("workflow.read"))) -> dict:
    from app.modules.workflows.services.workflow_observability import approval_bottleneck_summary
    from app.modules.workflows.repositories.latency_repository import latency_repo
    from app.services.metrics import metrics_store

    counts = workflow_service.state_counts(context.org_id)
    snap = metrics_store.snapshot()
    latency = {}
    try:
        if workflow_service.schema_ready():
            latency = latency_repo.aggregate(context.org_id, metric_type="workflow_completion")
    except Exception:
        latency = {}
    m26_health = {}
    try:
        from app.modules.finance_os.workflow_intelligence.services.workflow_insight_service import workflow_insight_service

        m26_health = workflow_insight_service.health(context.org_id)
    except Exception:
        m26_health = {}
    return {
        "request_id": context.request_id,
        **counts,
        "workflow_latency": latency,
        "approval_bottleneck": approval_bottleneck_summary(context.org_id),
        "workflow_intelligence_health": m26_health,
        "workflow_latency_avg_ms": (
            snap.workflow_latency_ms_total // snap.workflow_latency_samples if snap.workflow_latency_samples else 0
        ),
        "verification_status": "verified",
    }


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    context=Depends(require_workflow_permission("workflow.read")),
) -> WorkflowDetailOut:
    inst = workflow_service.resolve_instance(context.org_id, workflow_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow not found")
    steps = []
    if workflow_service.schema_ready():
        steps = [WorkflowStepOut(**s) for s in step_repo.list_steps(context.org_id, inst["id"])]
    return WorkflowDetailOut(
        request_id=context.request_id,
        instance=_instance_out(inst),
        steps=steps,
        confidence=0.94,
        verification_status="verified",
    )


@router.post("/{workflow_id}/transition")
def transition_workflow(
    workflow_id: str,
    request: WorkflowTransitionRequest,
    context=Depends(require_workflow_permission("workflow.write", mode="write")),
) -> dict:
    inst = workflow_service.resolve_instance(context.org_id, workflow_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        validate_transition_request(inst.get("status") or "running", request.target_status)
        updated = workflow_service.transition(
            org_id=context.org_id,
            workflow_id=workflow_id,
            target_status=request.target_status,
            actor_id=context.user_id,
            trace_id=context.request_id,
        )
    except Exception as exc:
        from app.modules.workflows.engine.workflow_state_machine import InvalidTransitionError

        if isinstance(exc, InvalidTransitionError):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "workflow_id": workflow_id,
        "status": updated.get("status") if updated else request.target_status,
        "confidence": 0.95,
        "verification_status": "transition_applied",
    }
