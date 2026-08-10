from app.core.config import DEV_ORG_ID
from app.services.langgraph_runner import run_langgraph_flow


class _OkDecision:
    allowed = True
    requires_human_approval = False
    reason = None
    code = None
    checks: list = []


class _NeedsApproval:
    allowed = True
    requires_human_approval = True
    reason = "human_approval_required"
    code = "HUMAN_APPROVAL_REQUIRED"
    checks: list = []


class _Denied:
    allowed = False
    requires_human_approval = False
    reason = "policy denied"
    code = "POLICY_DENIED"
    checks = ["policy_denied"]


def test_langgraph_flow_pending_approval(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_session_action",
        lambda *a, **k: _NeedsApproval(),
    )
    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_tool_invocation",
        lambda *a, **k: _OkDecision(),
    )
    result = run_langgraph_flow(
        org_id=DEV_ORG_ID,
        agent_type="ap_exception",
        trigger_type="invoice_exception_detected",
        payload={"action": "approve_payment", "amount": "90000", "use_legacy_langgraph": True},
        principal_roles=["tenant_admin"],
    )
    assert result["status"] == "pending_human_approval"
    assert len(result["proposed_actions"]) > 0
    assert "graph_runtime" in result
    assert "checkpoints" in result["graph_runtime"]
    assert any(cp["node"] == "policy_gate" for cp in result["graph_runtime"]["checkpoints"])


def test_langgraph_flow_completed(monkeypatch) -> None:
    from app.services import langgraph_runner

    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_session_action",
        lambda *a, **k: _OkDecision(),
    )
    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_tool_invocation",
        lambda *a, **k: _OkDecision(),
    )
    monkeypatch.setattr(
        langgraph_runner,
        "tool_adapter",
        lambda org_id, action, attrs=None, roles=None: {
            "status": "completed",
            "target": action.tool,
            "detail": "mocked",
            "response_code": 200,
        },
    )
    result = run_langgraph_flow(
        org_id=DEV_ORG_ID,
        agent_type="close_orchestration",
        trigger_type="schedule",
        payload={"action": "notify_user", "use_legacy_langgraph": True},
        principal_roles=["tenant_admin"],
    )
    assert result["status"] == "completed"
    assert "tool_results" in result
    assert "graph_runtime" in result
    runtime = result["graph_runtime"]
    assert runtime["graph_name"].endswith(".state_graph.v1")
    assert "execute_actions" in runtime["visited_nodes"]
