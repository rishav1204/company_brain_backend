from app.core.config import DEV_ORG_ID
from app.services import langgraph_runner


class _OkDecision:
    allowed = True
    requires_human_approval = False
    reason = None
    code = None
    checks: list = []


class _Denied:
    allowed = False
    requires_human_approval = False
    reason = "role not allowed"
    code = "POLICY_DENIED"
    checks = ["policy_denied"]


def test_state_runtime_policy_denied_includes_failure_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_session_action",
        lambda *a, **k: _Denied(),
    )
    result = langgraph_runner.run_langgraph_flow(
        org_id=DEV_ORG_ID,
        agent_type="ap_exception",
        trigger_type="invoice_exception_detected",
        payload={"action": "approve_payment", "amount": "1000", "use_legacy_langgraph": True},
        principal_roles=["ap_preparer"],
    )
    assert result["status"] == "failed"
    assert result["failure_contract"]["code"] == "POLICY_DENIED"
    checkpoints = result["graph_runtime"]["checkpoints"]
    assert any(cp["node"] == "policy_gate" and cp["status"] == "denied" for cp in checkpoints)


def test_state_runtime_action_failure_marks_run_failed(monkeypatch) -> None:
    def _fake_tool_adapter(org_id: str, action, attrs=None, roles=None):
        return {"status": "error", "detail": "simulated_failure", "target": "slack", "response_code": 500}

    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_session_action",
        lambda *a, **k: _OkDecision(),
    )
    monkeypatch.setattr(
        "app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_tool_invocation",
        lambda *a, **k: _OkDecision(),
    )
    monkeypatch.setattr(langgraph_runner, "tool_adapter", _fake_tool_adapter)
    result = langgraph_runner.run_langgraph_flow(
        org_id=DEV_ORG_ID,
        agent_type="close_orchestration",
        trigger_type="schedule",
        payload={"action": "notify_user", "use_legacy_langgraph": True},
        principal_roles=["tenant_admin"],
    )
    assert result["status"] == "failed"
    assert result["failure_contract"]["code"] == "DOWNSTREAM_ACTION_FAILED"
    assert any(cp["node"] == "execute_actions" and cp["status"] == "failed" for cp in result["graph_runtime"]["checkpoints"])
