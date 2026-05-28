from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.schemas.agents import (
    AgentApprovalRequest,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStateResponse,
)
from app.services.event_bus import event_bus
from app.services.action_service import execute_action
from app.services.langgraph_runner import run_langgraph_flow
from app.services.metrics import metrics_store
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.modules.core.iam.services.identity_resolver import same_actor
from app.services.policy_service import can_approve_agent_actions
from app.services.object_context import resolve_object_context
from app.services.principal_context import principal_from_request_context
from app.services.repositories import agents_repo, audit_repo

router = APIRouter(tags=["agents"])


@router.post("/agents/run", response_model=AgentRunResponse)
def run_agent(request: AgentRunRequest, context=Depends(build_request_context)) -> AgentRunResponse:
    enforce_finance_route_access(context, object_type="agent", mode="write", required_scope="agent.run")
    flow_result = run_langgraph_flow(
        org_id=context.org_id,
        agent_type=request.agent_type,
        trigger_type=request.trigger_type,
        payload=request.payload,
        principal_roles=context.roles,
        principal_attrs=context.attrs,
    )
    row = agents_repo.create_run(
        org_id=context.org_id,
        agent_type=request.agent_type,
        trigger_type=request.trigger_type,
        status=flow_result["status"],
        outputs={"message": "Run evaluated", "payload": request.payload, "flow_result": flow_result},
    )
    event_bus.publish(
        event_type="agent.run.started",
        org_id=context.org_id,
        source="api.agents",
        trace_id=context.request_id,
        payload={"run_id": row["run_id"], "agent_type": request.agent_type},
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="agent",
        actor_id=request.agent_type,
        event_type="agent.run.started",
        object_ref=f"agent_run:{row['run_id']}",
        payload_jsonb={"trigger_type": request.trigger_type},
    )
    metrics_store.incr_agent_run()
    return AgentRunResponse(
        request_id=context.request_id,
        run_id=row["run_id"],
        status=row["status"],
        confidence=0.95,
        verification_status="policy_checked",
    )


@router.get("/agents/runs/{run_id}", response_model=AgentRunStateResponse)
def get_agent_run(run_id: str, context=Depends(build_request_context)) -> AgentRunStateResponse:
    enforce_finance_route_access(context, object_type="agent", mode="read")
    row = agents_repo.get_run(org_id=context.org_id, run_id=run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return AgentRunStateResponse(
        request_id=context.request_id,
        run_id=row["run_id"],
        agent_type=row["agent_type"],
        trigger_type=row["trigger_type"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        outputs=row["outputs"],
        confidence=0.94,
        verification_status="verified",
    )


@router.post("/agents/runs/{run_id}/approve")
def approve_agent_run(run_id: str, request: AgentApprovalRequest, context=Depends(build_request_context)) -> dict:
    enforce_finance_route_access(context, action="approve", object_type="agent", mode="write")
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
        )
        outcome = "completed" if result.get("status") == "completed" else "failed"
        agents_repo.mark_action_outcome(org_id=context.org_id, action_id=action["action_id"], outcome=outcome)
        execution_results.append({"action_id": action["action_id"], "result": result})
    event_bus.publish(
        event_type="agent.action.approved",
        org_id=context.org_id,
        source="api.agents",
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
