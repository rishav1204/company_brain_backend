from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.finance_os.agents.orchestrator.agent_registry import AGENT_CATALOG
from app.modules.finance_os.agents.orchestrator.workflow_launcher import workflow_launcher
from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline
from app.modules.finance_os.agents.repositories.execution_repository import execution_repository
from app.modules.finance_os.agents.repositories.recommendation_repository import recommendation_repository
from app.modules.finance_os.agents.schemas.api_schema import FinanceAgentRunRequest, FinanceAgentRunResponse, WorkflowLaunchRequest
from app.modules.finance_os.agents.security.agents_guard import require_agent_read, require_agent_run
from app.schemas.agents import AgentApprovalRequest
from app.services.action_service import execute_action
from app.services.event_bus import event_bus
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.identity_resolver import same_actor
from app.services.policy_service import can_approve_agent_actions
from app.services.object_context import resolve_object_context
from app.services.principal_context import principal_from_request_context
from app.services.repositories import agents_repo, audit_repo
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-agents"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "module": "finance_os.agents",
        "schema_ready": execution_repository.schema_ready(),
    }


@router.get("/catalog")
def catalog(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    return {"agents": AGENT_CATALOG}


@router.post("/run", response_model=FinanceAgentRunResponse)
def run_agent(request: FinanceAgentRunRequest, context=Depends(build_request_context)) -> FinanceAgentRunResponse:
    require_agent_run(context.user)
    try:
        result = agent_orchestration_pipeline.run(
            context.org_id,
            request.agent_type,
            request.trigger_type,
            request.payload,
            trace_id=context.request_id,
            principal_roles=context.roles,
            principal_attrs=context.attrs,
            user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FinanceAgentRunResponse(**{k: result[k] for k in FinanceAgentRunResponse.model_fields if k in result})


@router.get("/executions")
def list_executions(
    agent_name: str | None = None,
    status: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_agent_read(context.user)
    items = execution_repository.list(context.org_id, agent_name=agent_name, status=status)
    return {"items": items, "count": len(items)}


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    row = execution_repository.get(context.org_id, execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")
    recs = recommendation_repository.list_for_execution(context.org_id, execution_id)
    return {"execution": row, "recommendations": recs}


@router.get("/recommendations")
def list_recommendations(
    status: str | None = None,
    agent_name: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_agent_read(context.user)
    items = recommendation_repository.list(context.org_id, status=status, agent_name=agent_name)
    return {"items": items, "count": len(items)}


@router.get("/recommendations/{recommendation_id}")
def get_recommendation(recommendation_id: str, context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    row = recommendation_repository.get(context.org_id, recommendation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"recommendation": row}


@router.get("/status")
def agent_status(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    return execution_repository.summary(context.org_id)


@router.post("/workflow")
def launch_workflow(request: WorkflowLaunchRequest, context=Depends(build_request_context)) -> dict:
    require_agent_run(context.user)
    rec = recommendation_repository.get(context.org_id, request.recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    workflow_key = request.workflow_key or (rec.get("metadata") or {}).get("plan", {}).get("workflow_key")
    if not workflow_key:
        raise HTTPException(status_code=400, detail="workflow_key required")
    wf = workflow_launcher.launch(
        context.org_id,
        workflow_key=workflow_key,
        user_id=context.user_id,
        metadata={"recommendation_id": request.recommendation_id},
        trace_id=context.request_id,
    )
    if not wf:
        raise HTTPException(status_code=503, detail="Workflow engine unavailable")
    recommendation_repository.update_status(
        context.org_id,
        request.recommendation_id,
        status="approved",
        workflow_instance_id=str(wf.get("workflow_id") or wf.get("id") or ""),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="agent.workflow.launched",
        object_ref=f"recommendation:{request.recommendation_id}",
        payload_jsonb={"workflow_key": workflow_key},
    )
    return {"workflow": wf}


@router.post("/runs/{run_id}/approve")
def approve_finance_agent_run(run_id: str, request: AgentApprovalRequest, context=Depends(build_request_context)) -> dict:
    require_agent_run(context.user)
    approval_decision = can_approve_agent_actions(context.roles, request.approved_by)
    if not approval_decision.allowed:
        raise HTTPException(status_code=403, detail=approval_decision.reason)
    if same_actor(context.org_id, context.user_id, request.approved_by):
        raise HTTPException(status_code=403, detail="Maker-checker violation: cannot approve own agent run")
    approved = agents_repo.approve_run(org_id=context.org_id, run_id=run_id)
    if not approved:
        raise HTTPException(status_code=404, detail="Agent run not found")
    pending_actions = agents_repo.list_pending_actions(org_id=context.org_id, run_id=run_id)
    execution_results = []
    for action in pending_actions:
        payload = action.get("payload_jsonb", {})
        params = payload.get("params", {})
        tool = str(payload.get("tool", action.get("target_system", "")))
        method = str(payload.get("method", action.get("action_type", "")))
        action_name = f"{tool}.{method}"
        object_type = str(params.get("object_type", "action"))
        object_id = str(params.get("object_id", action.get("action_id", ""))).strip()
        object_context = (
            resolve_object_context(org_id=context.org_id, object_type=object_type, object_id=object_id)
            if object_id
            else resolve_object_context(org_id=context.org_id, object_type=object_type, object_id=run_id)
        )
        policy_decision = evaluate_access(
            org_id=context.org_id,
            user_id=context.user_id,
            roles=context.roles,
            action=action_name,
            object_context=object_context,
            attrs=context.attrs,
            created_by=str(params.get("created_by") or params.get("owner_user_id") or ""),
            human_approved=True,
        )
        if not policy_decision.allowed:
            agents_repo.mark_action_outcome(org_id=context.org_id, action_id=action["action_id"], outcome="denied")
            execution_results.append(
                {"action_id": action["action_id"], "result": {"status": "error", "detail": policy_decision.reason}}
            )
            continue
        result = execute_action(
            org_id=context.org_id,
            actor_id=request.approved_by,
            tool=tool,
            method=method,
            params=params if isinstance(params, dict) else {},
            attrs=context.attrs,
            roles=context.roles,
            human_approved=True,
            source_acl=context.source_acl,
        )
        outcome = "executed" if result.get("status") == "completed" else "failed"
        agents_repo.mark_action_outcome(org_id=context.org_id, action_id=action["action_id"], outcome=outcome)
        execution_results.append({"action_id": action["action_id"], "result": result})
    event_bus.publish(
        event_type="agent.action.approved",
        org_id=context.org_id,
        source="finance_os.agents",
        trace_id=context.request_id,
        payload={"run_id": run_id, "approved_by": request.approved_by},
        principal=principal_from_request_context(context, human_approved=True),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=request.approved_by,
        event_type="agent.action.approved",
        object_ref=f"agent_run:{run_id}",
        payload_jsonb={"comment": request.comment},
    )
    return {
        "request_id": context.request_id,
        "run_id": run_id,
        "status": "approved",
        "executed_actions": execution_results,
        "confidence": 0.97,
        "verification_status": "human_approved",
    }
