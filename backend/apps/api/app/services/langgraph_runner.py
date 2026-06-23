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
        "workflow_intelligence_copilot": "workflow_intelligence_copilot",
        "workflow_intelligence_agent": "workflow_intelligence_copilot",
        "memory_copilot": "memory_copilot",
        "memory_agent": "memory_copilot",
        "graph_copilot": "graph_copilot",
        "graph_agent": "graph_copilot",
        "executive_copilot": "executive_copilot",
        "executive_agent": "executive_copilot",
        "audit_copilot": "audit_copilot",
        "audit_agent": "audit_copilot",
        "ap_agent": "ap_agent",
        "ap_exception": "ap_agent",
        "ap_exception_agent": "ap_agent",
        "reconciliation_agent": "reconciliation_agent",
        "gst_agent": "gst_agent",
        "close_agent": "close_agent",
        "close_orchestration": "close_agent",
        "close_orchestration_agent": "close_agent",
        "collections_agent": "collections_agent",
        "treasury_agent": "treasury_agent",
        "cashflow_risk": "treasury_agent",
        "cashflow_risk_agent": "treasury_agent",
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
    if agent_key in {"workflow_intelligence_copilot", "workflow_intelligence_agent"}:
        wf_type = str(state.payload.get("workflow_type") or "AP_INVOICE_APPROVAL")
        state.proposed_actions = [
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("owner_email", "finance-ops@example.com")),
                    "subject": f"Workflow intelligence advisory: {wf_type}",
                    "body": "Review bottleneck and SLA recommendations in Finance OS workflow intelligence.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "workflow_intelligence_rulebook", "count": 1})
        return
    if agent_key in {"memory_copilot", "memory_agent"}:
        query = str(state.payload.get("query") or state.payload.get("question") or "finance patterns")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": query, "top_k": int(state.payload.get("top_k", 8))},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "memory_rulebook", "count": 1})
        return
    if agent_key in {"graph_copilot", "graph_agent"}:
        entity_id = str(state.payload.get("entity_id") or state.payload.get("subject_ref") or "")
        state.proposed_actions = [
            ToolAction(
                tool="graph",
                method="traverse",
                params={"entity_id": entity_id, "max_depth": int(state.payload.get("max_depth", 6))},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "graph_rulebook", "count": 1})
        return
    if agent_key in {"executive_copilot", "executive_agent"}:
        query = str(state.payload.get("query") or state.payload.get("question") or "executive financial summary")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": query, "top_k": int(state.payload.get("top_k", 8))},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "executive_rulebook", "count": 1})
        return
    if agent_key in {"audit_copilot", "audit_agent"}:
        query = str(state.payload.get("query") or state.payload.get("question") or "audit timeline")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": query, "top_k": int(state.payload.get("top_k", 8))},
            ),
            ToolAction(
                tool="graph",
                method="traverse",
                params={"entity_id": str(state.payload.get("object_id") or ""), "max_depth": 4},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "audit_explorer_rulebook", "count": 2})
        return
    if agent_key == "ap_agent":
        entity_id = str(state.payload.get("entity_id") or state.payload.get("invoice_id") or "")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": f"AP invoice {entity_id}", "top_k": 5},
            ),
            ToolAction(
                tool="graph",
                method="traverse",
                params={"entity_id": entity_id, "max_depth": 4},
            ),
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("owner_email", "ap-ops@example.com")),
                    "subject": "AP agent review recommended",
                    "body": "Review AP exception and approve workflow if needed.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "ap_agent_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "reconciliation_agent":
        entity_id = str(state.payload.get("entity_id") or state.payload.get("bank_account_id") or "")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": "reconciliation mismatch", "entity_id": entity_id, "top_k": 5},
            ),
            ToolAction(
                tool="slack",
                method="postMessage",
                params={"channel": "#recon-alerts", "text": f"Reconciliation review for {entity_id}"},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "reconciliation_agent_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "gst_agent":
        entity_id = str(state.payload.get("entity_id") or state.payload.get("return_id") or "")
        state.proposed_actions = [
            ToolAction(
                tool="memory",
                method="search",
                params={"query": "GST compliance", "top_k": 5},
            ),
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("owner_email", "tax-ops@example.com")),
                    "subject": "GST review package ready",
                    "body": f"GST agent prepared review for {entity_id}; filing requires human approval.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "gst_agent_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "close_agent":
        state.proposed_actions = [
            ToolAction(
                tool="workflow",
                method="updateStatus",
                params={"workflow_id": state.payload.get("workflow_id"), "state": "close_orchestration_running"},
            ),
            ToolAction(
                tool="jira",
                method="createIssue",
                params={"summary": "Period close checklist", "description": "Agent-initiated close orchestration."},
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "close_agent_rulebook", "count": len(state.proposed_actions)})
        return
    if agent_key == "collections_agent":
        entity_id = str(state.payload.get("entity_id") or state.payload.get("invoice_id") or "")
        state.proposed_actions = [
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("customer_email", "collections@example.com")),
                    "subject": "Payment reminder",
                    "body": f"Collections follow-up recommended for {entity_id}.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "collections_agent_rulebook", "count": 1})
        return
    if agent_key == "treasury_agent":
        state.proposed_actions = [
            ToolAction(
                tool="email",
                method="send",
                params={
                    "to": str(state.payload.get("owner_email", "treasury@example.com")),
                    "subject": "Liquidity advisory",
                    "body": "Treasury agent detected liquidity risk; review cash position.",
                },
            ),
        ]
        state.checkpoint("plan_actions", "ok", {"planner": "treasury_agent_rulebook", "count": 1})
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
    from app.modules.finance_os.agents.orchestrator.forbidden_actions import (
        agent_tool_requires_approval,
        is_agent_tool_allowed,
        normalize_tool_method,
    )

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
    human_approved = bool(state.payload.get("human_approved"))
    principal_roles = state.principal_roles or ["viewer"]
    principal_user = str(state.principal_attrs.get("user_id") or "agent-system")

    requires_approval = requires_human_approval(
        action=action,
        amount=object_context.amount,
        vendor_risk=object_context.vendor_risk,
    )
    permission = evaluate_access(
        org_id=state.org_id,
        user_id=principal_user,
        roles=principal_roles,
        action=action,
        object_context=object_context,
        attrs=state.principal_attrs,
        created_by=str(state.payload.get("created_by") or state.payload.get("owner_user_id") or ""),
        human_approved=human_approved,
    )
    if not permission.allowed:
        state.status = "failed"
        state.failure_contract = {"code": "POLICY_DENIED", "retryable": False, "step": "policy_gate"}
        state.checkpoint("policy_gate", "denied", {"reason": permission.reason, "checks": permission.checks or []})
        return
    if requires_approval and not human_approved:
        state.status = "pending_human_approval"
        state.failure_contract = {"code": "HUMAN_APPROVAL_REQUIRED", "retryable": False, "step": "policy_gate"}
        state.checkpoint("policy_gate", "awaiting_approval", {"reason": "threshold_or_risk"})
        return

    for proposed in state.proposed_actions:
        tool = proposed.tool if hasattr(proposed, "tool") else str(proposed.get("tool", ""))
        method = proposed.method if hasattr(proposed, "method") else str(proposed.get("method", ""))
        if not is_agent_tool_allowed(tool, method):
            state.status = "failed"
            state.failure_contract = {
                "code": "TOOL_NOT_ALLOWED",
                "retryable": False,
                "step": "policy_gate",
                "detail": f"{tool}.{method}",
            }
            state.checkpoint("policy_gate", "denied", {"reason": "tool_not_allowed", "tool": tool, "method": method})
            return
        tool_l, method_l = normalize_tool_method(tool, method)
        tool_action = f"{tool_l}.{method_l}"
        tool_permission = evaluate_access(
            org_id=state.org_id,
            user_id=principal_user,
            roles=principal_roles,
            action=tool_action,
            object_context=object_context,
            attrs=state.principal_attrs,
            created_by=str(state.payload.get("created_by") or state.payload.get("owner_user_id") or ""),
            human_approved=human_approved,
        )
        if not tool_permission.allowed:
            state.status = "failed"
            state.failure_contract = {"code": "POLICY_DENIED", "retryable": False, "step": "policy_gate"}
            state.checkpoint(
                "policy_gate",
                "denied",
                {"reason": tool_permission.reason, "tool": tool, "method": method},
            )
            return
        if agent_tool_requires_approval(tool, method) and not human_approved:
            state.status = "pending_human_approval"
            state.failure_contract = {"code": "HUMAN_APPROVAL_REQUIRED", "retryable": False, "step": "policy_gate"}
            state.checkpoint("policy_gate", "awaiting_approval", {"reason": "tool_requires_approval", "tool": tool})
            return

    state.checkpoint("policy_gate", "allowed", {"checks": permission.checks or []})


def tool_adapter(org_id: str, action: ToolAction, attrs: dict | None = None, roles: list[str] | None = None) -> dict:
    from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_agent_tool_allowed, is_forbidden_action

    if is_forbidden_action(action.tool, action.method) or not is_agent_tool_allowed(action.tool, action.method):
        return {
            "status": "error",
            "target": action.tool,
            "detail": "forbidden_action",
            "response_code": 403,
        }
    principal_roles = roles or (attrs or {}).get("roles") or ["viewer"]
    actor_id = str((attrs or {}).get("user_id") or "agent-runtime")
    human_approved = bool((attrs or {}).get("human_approved"))
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
                    actor_id=actor_id,
                )
            except Exception as exc:
                return {
                    "status": "error",
                    "target": "workflow",
                    "detail": str(exc),
                    "response_code": 409,
                }
        return {"status": "completed", "target": "workflow", "detail": "workflow_state_updated", "response_code": 200}
    if action.tool == "memory" and action.method == "search":
        return execute_action(
            org_id=org_id,
            actor_id=actor_id,
            tool="memory",
            method="search",
            params=action.params,
            attrs=attrs,
            roles=principal_roles,
            human_approved=human_approved,
        )
    if action.tool == "graph" and action.method == "traverse":
        return execute_action(
            org_id=org_id,
            actor_id=actor_id,
            tool="graph",
            method="traverse",
            params=action.params,
            attrs=attrs,
            roles=principal_roles,
            human_approved=human_approved,
        )
    if action.tool in {"slack", "email", "jira", "linear", "erp"}:
        method = action.method
        if action.tool == "email" and method == "postMessage":
            method = "send"
        if action.tool == "erp" and method == "updateStatus":
            method = "writeback"
        return execute_action(
            org_id=org_id,
            actor_id=actor_id,
            tool=action.tool,
            method=method,
            params=action.params,
            attrs=attrs,
            roles=principal_roles,
            human_approved=human_approved,
        )
    return {"status": "error", "target": action.tool, "detail": "unsupported_tool", "response_code": 400}


def _execute_actions_node(state: GraphRuntimeState) -> None:
    from app.modules.finance_os.agents.orchestrator.forbidden_actions import filter_actions

    allowed, blocked = filter_actions(state.proposed_actions)
    if blocked:
        state.status = "failed"
        state.failure_contract = {
            "code": "FORBIDDEN_ACTION",
            "retryable": False,
            "step": "tool_execution",
            "detail": ",".join(blocked),
        }
        state.checkpoint("execute_actions", "blocked", {"blocked": blocked})
        return
    state.tool_results = [
        tool_adapter(state.org_id, action, attrs=state.principal_attrs, roles=state.principal_roles)
        for action in allowed
    ]
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
        principal_roles=principal_roles or ["viewer"],
        principal_attrs=principal_attrs or {},
    )
    state.checkpoint("init", "entered", {"agent_type": agent_type, "trigger_type": trigger_type})

    agent_context = payload.get("agent_context") if isinstance(payload, dict) else None
    if agent_context:
        state.payload["agent_context"] = agent_context

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
