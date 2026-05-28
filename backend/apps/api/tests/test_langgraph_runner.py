from app.services.langgraph_runner import run_langgraph_flow


def test_langgraph_flow_pending_approval() -> None:
    result = run_langgraph_flow(
        org_id="org-demo",
        agent_type="ap_exception",
        trigger_type="invoice_exception_detected",
        payload={"action": "approve_payment", "amount": "90000"},
    )
    assert result["status"] == "pending_human_approval"
    assert len(result["proposed_actions"]) > 0
    assert "graph_runtime" in result
    assert "checkpoints" in result["graph_runtime"]
    assert any(cp["node"] == "policy_gate" for cp in result["graph_runtime"]["checkpoints"])


def test_langgraph_flow_completed(monkeypatch) -> None:
    from app.services import langgraph_runner

    monkeypatch.setattr(
        langgraph_runner,
        "tool_adapter",
        lambda org_id, action, attrs=None: {
            "status": "completed",
            "target": action.tool,
            "detail": "mocked",
            "response_code": 200,
        },
    )
    result = run_langgraph_flow(
        org_id="org-demo",
        agent_type="close_orchestration",
        trigger_type="schedule",
        payload={"action": "notify_user"},
    )
    assert result["status"] == "completed"
    assert "tool_results" in result
    assert "graph_runtime" in result
    runtime = result["graph_runtime"]
    assert runtime["graph_name"].endswith(".state_graph.v1")
    assert "execute_actions" in runtime["visited_nodes"]
