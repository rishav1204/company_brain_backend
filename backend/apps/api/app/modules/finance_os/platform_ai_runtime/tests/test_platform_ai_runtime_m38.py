from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import goal_planner
from app.modules.finance_os.platform_ai_runtime.engine.observer import observer
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, WorldState


def test_execution_graph_dag_order() -> None:
    graph = ExecutionGraph()
    graph.add_node(GraphNodeSpec(id="a", tool="memory", method="search", label="A"))
    graph.add_node(GraphNodeSpec(id="b", tool="graph", method="traverse", label="B", depends_on=["a"]))
    assert graph.next_ready_node().id == "a"
    graph.mark_complete("a")
    assert graph.next_ready_node().id == "b"
    graph.mark_complete("b")
    assert graph.all_complete() is True


def test_execution_graph_has_failed() -> None:
    graph = ExecutionGraph()
    graph.add_node(GraphNodeSpec(id="x", tool="ap", method="list_invoices", label="X"))
    graph.mark_failed("x")
    assert graph.has_failed() is True
    assert graph.all_complete() is False


def test_goal_planner_procurement_heuristic() -> None:
    graph, meta = goal_planner.plan("Buy 5 laptops from vendor for inventory", use_llm=False)
    assert len(graph.nodes) >= 4
    assert meta.approval_points
    assert "procurement" in meta.reasoning.lower() or "po" in meta.reasoning.lower()


def test_goal_planner_collections_heuristic() -> None:
    graph, meta = goal_planner.plan("Follow up on overdue collections", use_llm=False)
    tools = {(n.tool, n.method) for n in graph.nodes.values()}
    assert ("ar", "list_overdue") in tools
    assert meta.reasoning


def test_goal_planner_period_close_heuristic() -> None:
    graph, _ = goal_planner.plan("Run period close checklist", use_llm=False)
    assert len(graph.nodes) == 9
    tools = {n.tool for n in graph.nodes.values()}
    assert "fiscal" in tools
    assert "treasury" in tools


def test_observer_insufficient_cash_alternatives() -> None:
    node = GraphNodeSpec(id="s1", tool="treasury", method="get_cash_position", label="Cash")
    result = {"status": "blocked", "reason": "insufficient_cash", "facts": {"available": 100, "required": 500}}
    obs = observer.analyze(node, result, world_state=WorldState())
    assert obs.blocked is True
    assert obs.alternatives


def test_consume_goal_triggers_import() -> None:
    from app.services.event_consumers import _consume_goal_triggers

    assert callable(_consume_goal_triggers)


@patch("app.modules.finance_os.platform_ai_runtime.goals.goal_manager.runtime_service")
@patch("app.modules.finance_os.platform_ai_runtime.goals.goal_manager.goal_repository")
def test_goal_manager_handle_event(mock_repo, mock_runtime) -> None:
    from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

    mock_repo.schema_ready = MagicMock(return_value=True)
    mock_runtime.schema_ready.return_value = True
    mock_runtime.chat.return_value = MagicMock(model_dump=lambda: {"status": "plan_pending_approval"})

    out = goal_manager.handle_event(
        "11111111-1111-4111-8111-111111111111",
        event_type="invoice.due",
        payload={"invoice_id": "inv-1"},
    )
    assert out is not None
    mock_runtime.chat.assert_called_once()


@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.audit_repo")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.tool_registry")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.executor")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.goal_repository")
def test_runtime_pauses_on_approval(mock_repo, mock_executor, mock_registry, mock_audit) -> None:
    from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
    from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import PlanMetadata
    from app.modules.finance_os.platform_ai_runtime.services.runtime_service import RuntimeService

    mock_registry.is_read_only.return_value = False
    graph = ExecutionGraph()
    graph.add_node(GraphNodeSpec(
        id="step_1", tool="procurement", method="create_po", label="Create PO", requires_approval=True,
    ))
    mock_repo.get_goal.return_value = {"plan_metadata": {}, "world_state": {}}
    mock_repo.get_run.return_value = {"id": "run-1"}
    mock_repo.get_latest_graph.return_value = graph.to_dict()

    svc = RuntimeService()
    resp = svc._execute_loop(
        "org-1",
        goal_id="g1",
        run_id="run-1",
        graph=graph,
        plan_meta=PlanMetadata(reasoning="test"),
        world_state=WorldState(),
        user_id="u1",
        roles=["tenant_admin"],
        attrs={"user_id": "u1"},
        human_approved=False,
        assistant_prefix="Plan",
    )
    assert resp.approval_required is True
    assert resp.status == "plan_pending_approval"
    mock_executor.run.assert_not_called()
