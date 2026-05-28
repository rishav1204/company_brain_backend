from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import build_request_context
from app.core.config import settings
from app.schemas.workflows import (
    WorkflowActionRequest,
    WorkflowItem,
    WorkflowListResponse,
    WorkflowTimelineItem,
    WorkflowTimelineResponse,
)
from app.services.dev_workflows import list_dev_workflows, postgres_configured
from app.services.event_bus import event_bus
from app.services.idempotency import idempotency_service
from app.services.metrics import metrics_store
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.approval_gate_service import pending_approval_response_reason
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.modules.core.iam.services.rbac_service import can_access_sensitive_field
from app.services.principal_context import principal_from_request_context
from app.modules.workflows.events.workflow_events import emit_workflow_completed
from app.modules.workflows.services.workflow_service import workflow_service
from app.services.repositories import audit_repo, workflows_repo
from app.services.workflow_presenter import present_workflow

router = APIRouter(tags=["workflows"])


def _load_workflows(
    org_id: str,
    workflow_type: str | None,
    status: str | None,
    limit: int,
) -> list[dict]:
    use_postgres = postgres_configured() and (
        settings.app_env.lower() != "dev" or settings.dev_use_postgres
    )
    if use_postgres:
        try:
            if workflow_service.schema_ready():
                return workflow_service.list_for_api(
                    org_id, workflow_type=workflow_type, status=status, limit=limit
                )
            return workflows_repo.list_workflows(
                org_id=org_id,
                workflow_type=workflow_type,
                status=status,
                limit=limit,
            )
        except Exception:
            if settings.app_env.lower() != "dev":
                raise HTTPException(status_code=503, detail="Database unavailable") from None
    if settings.app_env.lower() != "dev":
        raise HTTPException(status_code=503, detail="Database unavailable")
    return list_dev_workflows(
        org_id=org_id,
        workflow_type=workflow_type,
        status=status,
        limit=limit,
    )


@router.get("/workflows", response_model=WorkflowListResponse)
def list_workflows(
    context=Depends(build_request_context),
    workflow_type: str | None = Query(default=None, alias="type"),
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> WorkflowListResponse:
    enforce_finance_route_access(context, object_type="workflow", mode="read")
    rows = _load_workflows(context.org_id, workflow_type, status, limit)
    items = [present_workflow(row) for row in rows]
    verification = "verified" if postgres_configured() else "dev_sample_data"
    return WorkflowListResponse(
        request_id=context.request_id,
        items=items,
        workflows=items,
        confidence=0.96 if postgres_configured() else 0.85,
        verification_status=verification,
    )


@router.post("/workflows/{workflow_id}/actions")
def execute_workflow_action(
    workflow_id: str,
    request: WorkflowActionRequest,
    context=Depends(build_request_context),
) -> dict:
    enforce_finance_route_access(context, action=request.action, object_type="workflow", mode="write")
    workflow = workflow_service.resolve_instance(context.org_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    legacy_id = workflow.get("legacy_workflow_id") or workflow_id
    if workflow_service.schema_ready():
        workflow_service.ensure_instance_for_legacy(context.org_id, {
            "id": legacy_id,
            "workflow_type": workflow.get("workflow_type", "generic"),
            "owner_user_id": workflow.get("started_by"),
            "state": workflow.get("status", "running"),
        })

    idempotency_key = request.parameters.get("idempotency_key")
    if isinstance(idempotency_key, str) and idempotency_service.is_replay(workflow_id=workflow_id, key=idempotency_key):
        return {
            "request_id": context.request_id,
            "workflow_id": workflow_id,
            "accepted": True,
            "idempotent_replay": True,
            "confidence": 0.99,
            "verification_status": "idempotent_replay",
        }

    amount = request.parameters.get("amount")
    vendor_risk = request.parameters.get("vendor_risk")
    restricted_fields = {"bank_account_number", "tax_id", "salary", "ssn"}
    for field in restricted_fields:
        if field in request.parameters and not can_access_sensitive_field(
            context.org_id, context.user_id, context.roles, field
        ):
            raise HTTPException(status_code=403, detail=f"Field-level ACL denied for {field}")
    parsed_amount: float | None = None
    if amount is not None and str(amount).strip():
        try:
            parsed_amount = float(amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid amount in parameters")
    from app.services.object_context import resolve_object_context

    object_context = resolve_object_context(
        org_id=context.org_id,
        object_type="workflow",
        object_id=workflow_id,
    )
    object_context.amount = parsed_amount
    object_context.vendor_risk = str(vendor_risk) if vendor_risk else None
    branch_id = request.parameters.get("branch_id")
    company_id = request.parameters.get("company_id")
    if branch_id:
        object_context.branch_id = str(branch_id)
    if company_id:
        object_context.company_id = str(company_id)

    human_approved = bool(request.parameters.get("human_approved") or request.parameters.get("approved"))
    policy_decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles,
        action=request.action,
        object_context=object_context,
        attrs=context.attrs,
        created_by=workflow.get("started_by") or workflow.get("owner_user_id") or request.parameters.get("created_by"),
        human_approved=human_approved,
        object_branch_id=object_context.branch_id,
        object_company_id=object_context.company_id,
    )
    if not policy_decision.allowed:
        if pending_approval_response_reason(policy_decision.reason):
            return {
                "request_id": context.request_id,
                "workflow_id": workflow_id,
                "accepted": False,
                "requires_human_approval": True,
                "reason": policy_decision.reason,
                "confidence": 0.97,
                "verification_status": "policy_blocked_pending_approval",
            }
        raise HTTPException(status_code=403, detail=policy_decision.reason)

    workflows_repo.add_timeline_step(
        org_id=context.org_id,
        workflow_id=legacy_id,
        step_type="workflow.action.executed",
        state="executed",
    )
    if workflow_service.schema_ready() and human_approved:
        try:
            workflow_service.transition(
                org_id=context.org_id,
                workflow_id=workflow_id,
                target_status="approved",
                actor_id=context.user_id,
                trace_id=context.request_id,
            )
            emit_workflow_completed(context.org_id, workflow.get("id", workflow_id), trace_id=context.request_id)
        except Exception:
            pass
    event_bus.publish(
        event_type="agent.action.executed",
        org_id=context.org_id,
        source="api.workflows",
        trace_id=context.request_id,
        payload={"workflow_id": workflow_id, "action": request.action},
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="agent.action.executed",
        object_ref=f"workflow:{workflow_id}",
        payload_jsonb={"action": request.action, "parameters": request.parameters},
    )
    if isinstance(idempotency_key, str) and idempotency_key:
        idempotency_service.mark(workflow_id=workflow_id, key=idempotency_key)
    metrics_store.incr_workflow_action()
    return {
        "request_id": context.request_id,
        "workflow_id": workflow_id,
        "accepted": True,
        "confidence": 0.95,
        "verification_status": "policy_checked",
    }


@router.get("/workflows/{workflow_id}/timeline", response_model=WorkflowTimelineResponse)
def workflow_timeline(workflow_id: str, context=Depends(build_request_context)) -> WorkflowTimelineResponse:
    enforce_finance_route_access(context, object_type="workflow", mode="read")
    workflow = workflow_service.resolve_instance(context.org_id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    legacy_id = workflow.get("legacy_workflow_id") or workflow_id
    if workflow_service.schema_ready():
        workflow_service.ensure_instance_for_legacy(context.org_id, {
            "id": legacy_id,
            "workflow_type": workflow.get("workflow_type", "generic"),
            "owner_user_id": workflow.get("started_by"),
            "state": workflow.get("status", "running"),
        })
    rows = [
        WorkflowTimelineItem(**row)
        for row in workflow_service.list_timeline(org_id=context.org_id, workflow_id=workflow_id)
    ]
    return WorkflowTimelineResponse(
        request_id=context.request_id,
        workflow_id=workflow_id,
        timeline=rows,
        confidence=0.94,
        verification_status="verified",
    )
