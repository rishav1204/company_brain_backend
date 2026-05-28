from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.services.action_service import execute_action
from app.services.llm_provider import llm_provider
from app.services.logger import log_event
from app.modules.core.iam.services.access_control import evaluate_access
from app.services.policy_service import evaluate_permission, requires_human_approval
from app.services.object_context import ObjectContext, resolve_object_context


@dataclass
class ToolAction:
    tool: str
    method: str
    params: dict


@dataclass
class GraphCheckpoint:
    node: str
    status: str
    at: str
    detail: dict = field(default_factory=dict)


@dataclass
class GraphRuntimeState:
    run_id: str
    graph_name: str
    org_id: str
    agent_type: str
    trigger_type: str
    payload: dict
    principal_roles: list[str]
    principal_attrs: dict
    current_node: str = "init"
    visited_nodes: list[str] = field(default_factory=list)
    checkpoints: list[GraphCheckpoint] = field(default_factory=list)
    proposed_actions: list[ToolAction] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    status: str = "running"
    failure_contract: dict | None = None

    def checkpoint(self, node: str, status: str, detail: dict | None = None) -> None:
        self.current_node = node
        self.visited_nodes.append(node)
        self.checkpoints.append(
            GraphCheckpoint(
                node=node,
                status=status,
                at=datetime.now(timezone.utc).isoformat(),
                detail=detail or {},
            )
        )


def _normalize_agent_key(agent_type: str) -> str:
    key = agent_type.strip().lower()
    mapping = {
        "ap_exception": "ap_exception_agent",
        "ap_exception_agent": "ap_exception_agent",
        "close_orchestration": "close_orchestration_agent",
        "close_orchestration_agent": "close_orchestration_agent",
        "cashflow_risk": "cashflow_risk_agent",
        "cashflow_risk_agent": "cashflow_risk_agent",
    }
    return mapping.get(key, key)


def _default_actions(state: GraphRuntimeState) -> list[ToolAction]:
    return [
        ToolAction(
            tool="workflow",
            method="updateStatus",
            params={"workflow_id": state.payload.get("workflow_id"), "state": "under_review"},
        ),
        ToolAction(
            tool="slack",
            method="postMessage",
            params={"channel": "#finance-alerts", "text": f"{state.agent_type} triggered from {state.trigger_type}"},
        ),
    ]


def _plan_actions_node(state: GraphRuntimeState) -> None:
    agent_key = _normalize_agent_key(state.agent_type)
    if agent_key == "ap_exception_agent":
        state.proposed_actions = [
            ToolAction(
                tool="workflow",
                method="updateStatus",
                params={"workflow_id": state.payload.get("workflow_id"), "state": "ap_exception_review"},
            ),
            ToolAction(
                tool="slack",
                method="postMessage",
                params={"channel": "#ap-alerts", "text": "AP exception detected; review initiated."},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "domain_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "close_orchestration_agent":
        state.proposed_actions = [
            ToolAction(
                tool="workflow",
                method="updateStatus",
                params={"workflow_id": state.payload.get("workflow_id"), "state": "close_orchestration_running"},
            ),
            ToolAction(
                tool="jira",
                method="createIssue",
                params={"summary": "Close blocker triage", "description": "Investigate close blockers for current period."},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "domain_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "cashflow_risk_agent":
        state.proposed_actions = [
            ToolAction(
                tool="workflow",
                method="updateStatus",
                params={"workflow_id": state.payload.get("workflow_id"), "state": "cashflow_risk_assessed"},
            ),
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("owner_email", "finance-ops@example.com")),
                    "subject": "Cashflow risk alert",
                    "body": "Risk threshold exceeded; review recommended.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "domain_rulebook", "count": len(state.proposed_actions)})
        return

    if llm_provider.is_ready():
        prompt = (
            f"Agent type: {state.agent_type}\n"
            f"Trigger type: {state.trigger_type}\n"
            f"Payload: {json.dumps(state.payload)}\n"
            "Return JSON with key `actions`, list of actions. "
            "Each action has: tool, method, params."
        )
        try:
            llm_output = llm_provider.generate_json(
                org_id=state.org_id,
                system_prompt="You are a finance operations agent planner that outputs strict JSON only.",
                user_prompt=prompt,
                estimated_tokens=1800,
            )
            actions = llm_output.get("actions", [])
            state.proposed_actions = [
                ToolAction(
                    tool=str(action.get("tool", "workflow")),
                    method=str(action.get("method", "updateStatus")),
                    params=action.get("params", {}),
                )
                for action in actions
            ]
            if not state.proposed_actions:
                state.proposed_actions = _default_actions(state)
            state.checkpoint("plan_actions", "ok", {"planner": "llm", "count": len(state.proposed_actions)})
            return
        except Exception as exc:
            log_event("llm.workflow_step.failed", org_id=state.org_id, step="plan_actions", error=str(exc))
            state.proposed_actions = _default_actions(state)
            state.checkpoint("plan_actions", "fallback", {"planner": "llm_fallback", "error": str(exc)})
            return

    state.proposed_actions = _default_actions(state)
    state.checkpoint("plan_actions", "ok", {"planner": "default", "count": len(state.proposed_actions)})


def _policy_gate_node(state: GraphRuntimeState) -> None:
    amount_raw = state.payload.get("amount")
    parsed_amount: float | None = None
    if amount_raw is not None and str(amount_raw).strip():
        try:
            parsed_amount = float(amount_raw)
        except (TypeError, ValueError):
            parsed_amount = None
    action = str(state.payload.get("action", "notify_user"))
    object_type = str(state.payload.get("object_type", "workflow"))
    object_id = str(state.payload.get("object_id", "")).strip()
    if object_id:
        object_context = resolve_object_context(org_id=state.org_id, object_type=object_type, object_id=object_id)
        if parsed_amount is not None and object_context.amount is None:
            object_context.amount = parsed_amount
        if state.payload.get("vendor_risk") and not object_context.vendor_risk:
            object_context.vendor_risk = str(state.payload.get("vendor_risk"))
    else:
        object_context = ObjectContext(
            object_type=object_type,
            object_id="",
            amount=parsed_amount,
            vendor_risk=str(state.payload.get("vendor_risk")) if state.payload.get("vendor_risk") else None,
        )
    requires_approval = requires_human_approval(
        action=action,
        amount=object_context.amount,
        vendor_risk=object_context.vendor_risk,
    )
    permission = evaluate_access(
        org_id=state.org_id,
        user_id=str(state.principal_attrs.get("user_id") or "agent-system"),
        roles=state.principal_roles or ["tenant_admin"],
        action=action,
        object_context=object_context,
        attrs=state.principal_attrs,
        created_by=str(state.payload.get("created_by") or state.payload.get("owner_user_id") or ""),
    )
    if not permission.allowed:
        state.status = "failed"
        state.failure_contract = {"code": "POLICY_DENIED", "retryable": False, "step": "policy_gate"}
        state.checkpoint("policy_gate", "denied", {"reason": permission.reason, "checks": permission.checks or []})
        return
    if requires_approval:
        state.status = "pending_human_approval"
        state.failure_contract = {"code": "HUMAN_APPROVAL_REQUIRED", "retryable": False, "step": "policy_gate"}
        state.checkpoint("policy_gate", "awaiting_approval", {"reason": "threshold_or_risk"})
        return
    state.checkpoint("policy_gate", "allowed", {"checks": permission.checks or []})


def tool_adapter(org_id: str, action: ToolAction, attrs: dict | None = None) -> dict:
    if action.tool == "workflow":
        from app.modules.workflows.engine.workflow_state_machine import legacy_state_to_status
        from app.modules.workflows.services.workflow_service import workflow_service

        workflow_id = str(action.params.get("workflow_id") or "")
        target_state = str(action.params.get("state") or action.params.get("status") or "running")
        target_status = legacy_state_to_status(target_state)
        if workflow_id and workflow_service.schema_ready():
            try:
                workflow_service.transition(
                    org_id=org_id,
                    workflow_id=workflow_id,
                    target_status=target_status,
                    actor_id="agent-runtime",
                )
            except Exception as exc:
                return {
                    "status": "error",
                    "target": "workflow",
                    "detail": str(exc),
                    "response_code": 409,
                }
        return {"status": "completed", "target": "workflow", "detail": "workflow_state_updated", "response_code": 200}
    if action.tool in {"slack", "email", "jira", "linear", "erp"}:
        method = action.method
        if action.tool == "email" and method == "postMessage":
            method = "send"
        if action.tool == "erp" and method == "updateStatus":
            method = "writeback"
        return execute_action(
            org_id=org_id,
            actor_id="agent-runtime",
            tool=action.tool,
            method=method,
            params=action.params,
            attrs=attrs,
            roles=["tenant_admin"],
            human_approved=False,
        )
    return {"status": "error", "target": action.tool, "detail": "unsupported_tool", "response_code": 400}


def _execute_actions_node(state: GraphRuntimeState) -> None:
    state.tool_results = [tool_adapter(state.org_id, action, attrs=state.principal_attrs) for action in state.proposed_actions]
    failed = [item for item in state.tool_results if str(item.get("status", "")).lower() != "completed"]
    if failed:
        first_error = str(failed[0].get("detail", "execution_failed"))
        state.status = "failed"
        state.failure_contract = {
            "code": "DOWNSTREAM_ACTION_FAILED",
            "retryable": False,
            "step": "tool_execution",
            "detail": first_error,
        }
        state.checkpoint("execute_actions", "failed", {"failed_count": len(failed)})
        return
    state.status = "completed"
    state.checkpoint("execute_actions", "completed", {"count": len(state.tool_results)})


def _runtime_payload(state: GraphRuntimeState) -> dict:
    return {
        "graph_name": state.graph_name,
        "run_id": state.run_id,
        "current_node": state.current_node,
        "visited_nodes": state.visited_nodes,
        "checkpoints": [
            {"node": item.node, "status": item.status, "at": item.at, "detail": item.detail} for item in state.checkpoints
        ],
    }


def run_langgraph_flow(
    org_id: str,
    agent_type: str,
    trigger_type: str,
    payload: dict,
    principal_roles: list[str] | None = None,
    principal_attrs: dict | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    state = GraphRuntimeState(
        run_id=str(uuid4()),
        graph_name=f"{_normalize_agent_key(agent_type)}.state_graph.v1",
        org_id=org_id,
        agent_type=agent_type,
        trigger_type=trigger_type,
        payload=payload if isinstance(payload, dict) else {},
        principal_roles=principal_roles or ["tenant_admin"],
        principal_attrs=principal_attrs or {},
    )
    state.checkpoint("init", "entered", {"agent_type": agent_type, "trigger_type": trigger_type})

    _plan_actions_node(state)
    _policy_gate_node(state)
    if state.status == "running":
        _execute_actions_node(state)
    if state.status == "running":
        state.status = "completed"
    state.checkpoint("finalize", state.status, {"has_failure_contract": bool(state.failure_contract)})

    response = {
        "status": state.status,
        "executed_at": now,
        "proposed_actions": [action.__dict__ for action in state.proposed_actions],
        "graph_runtime": _runtime_payload(state),
    }
    if state.tool_results:
        response["tool_results"] = state.tool_results
    if state.failure_contract:
        response["failure_contract"] = state.failure_contract
    return response
