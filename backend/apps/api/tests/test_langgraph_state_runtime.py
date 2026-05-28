from app.services import langgraph_runner


def test_state_runtime_policy_denied_includes_failure_contract() -> None:
    result = langgraph_runner.run_langgraph_flow(
        org_id="org-demo",
        agent_type="ap_exception",
        trigger_type="invoice_exception_detected",
        payload={"action": "approve_payment", "amount": "1000"},
        principal_roles=["ap_preparer"],
    )
    assert result["status"] == "failed"
    assert result["failure_contract"]["code"] == "POLICY_DENIED"
    checkpoints = result["graph_runtime"]["checkpoints"]
    assert any(cp["node"] == "policy_gate" and cp["status"] == "denied" for cp in checkpoints)


def test_state_runtime_action_failure_marks_run_failed(monkeypatch) -> None:
    def _fake_tool_adapter(org_id: str, action, attrs=None):
        return {"status": "error", "detail": "simulated_failure", "target": "slack", "response_code": 500}

    monkeypatch.setattr(langgraph_runner, "tool_adapter", _fake_tool_adapter)
    result = langgraph_runner.run_langgraph_flow(
        org_id="org-demo",
        agent_type="close_orchestration",
        trigger_type="schedule",
        payload={"action": "notify_user"},
        principal_roles=["tenant_admin"],
    )
    assert result["status"] == "failed"
    assert result["failure_contract"]["code"] == "DOWNSTREAM_ACTION_FAILED"
    assert any(cp["node"] == "execute_actions" and cp["status"] == "failed" for cp in result["graph_runtime"]["checkpoints"])
