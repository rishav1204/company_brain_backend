from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import goal_planner
from app.modules.finance_os.platform_ai_runtime.engine.rollback_manager import rollback_manager
from app.modules.finance_os.platform_ai_runtime.engine.self_correction import self_correction
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, ObservationResult


def test_period_close_has_nine_steps() -> None:
    graph, meta = goal_planner.plan("Run period close checklist", use_llm=False)
    assert len(graph.nodes) == 9
    assert "fiscal" in meta.reasoning.lower() or "close" in meta.reasoning.lower()


def test_self_correction_apply_alternative() -> None:
    alts = [{"action": "payment.postpone", "label": "Postpone 7 days"}]
    node = self_correction.apply_alternative(alts, 0)
    assert node is not None
    assert node.tool == "payment"
    assert node.method == "postpone"


def test_rollback_forensics_context() -> None:
    with patch("app.modules.platform.governance.services.forensics_service.forensics_service") as mock_f:
        mock_f.rollback_analysis.return_value = {"chain": []}
        out = rollback_manager.forensics_context("org", entity_type="procurement", entity_id="po-1")
        assert out == {"chain": []}


@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.billing_ai_operation")
@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.goal_repository")
def test_resume_run(mock_repo, mock_billing) -> None:
    from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
    from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import PlanMetadata, WorldState
    from app.modules.finance_os.platform_ai_runtime.services.runtime_service import RuntimeService

    mock_billing.return_value.__enter__ = MagicMock(return_value=None)
    mock_billing.return_value.__exit__ = MagicMock(return_value=None)
    graph = ExecutionGraph()
    graph.add_node(GraphNodeSpec(id="s1", tool="ap", method="list_invoices", label="List", status="completed"))
    graph.add_node(GraphNodeSpec(id="s2", tool="ar", method="list_overdue", label="Overdue", depends_on=["s1"]))
    mock_repo.get_goal.return_value = {"plan_metadata": {}, "world_state": {}}
    mock_repo.get_run.return_value = {"id": "run-1"}
    mock_repo.get_latest_graph.return_value = graph.to_dict()

    svc = RuntimeService()
    with patch.object(svc, "_execute_loop") as mock_loop:
        mock_loop.return_value = MagicMock(status="executing", progress_percent=50.0)
        svc.resume_run("org", goal_id="g1", run_id="run-1", user_id="u1")
        mock_repo.update_run.assert_called()
        mock_loop.assert_called_once()


@patch("app.modules.finance_os.platform_ai_runtime.goals.goal_manager.goal_repository")
def test_goal_manager_create_or_resume_new(mock_repo) -> None:
    from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

    mock_repo.list_goals.return_value = []
    with patch("app.modules.finance_os.platform_ai_runtime.goals.goal_manager.runtime_service") as mock_rt:
        mock_rt.schema_ready.return_value = True
        mock_rt.chat.return_value = MagicMock(model_dump=lambda: {"status": "plan_pending_approval"})
        out = goal_manager.create_or_resume("org", title="Daily collections", message="List overdue AR")
        assert out is not None
        mock_rt.chat.assert_called_once()


@patch("app.modules.finance_os.agents.repositories.execution_repository.execution_repository")
@patch("app.modules.finance_os.platform_ai_runtime.goals.goal_manager.goal_repository")
def test_approval_queue_m38_and_m29(mock_repo, mock_exec_repo) -> None:
    from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

    mock_repo.list_pending_runs.return_value = [{"run_id": "r1", "goal_id": "g1", "title": "Test", "status": "pending_approval"}]
    mock_exec_repo.schema_ready.return_value = True
    mock_exec_repo.list.return_value = [{"id": "e1", "agent_name": "ap_agent", "status": "pending_approval", "created_at": "2026-01-01"}]
    items = goal_manager.list_approval_queue("org")
    sources = {i.source for i in items}
    assert "m38" in sources
    assert "m29" in sources


def test_consume_m38_scheduler_import() -> None:
    from app.services.event_consumers import _consume_m38_scheduler

    assert callable(_consume_m38_scheduler)


@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.runtime_service")
def test_m29_delegate_to_m38(mock_rt) -> None:
    from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline

    mock_rt.schema_ready.return_value = True
    mock_rt.chat.return_value = MagicMock(
        status="completed",
        goal_run_id="run-1",
        goal_id="g1",
        mode="completed",
        progress_percent=100.0,
        plan=MagicMock(confidence=85, confidence_band="strong"),
        model_dump=lambda: {"status": "completed"},
    )
    out = agent_orchestration_pipeline._try_m38_delegate(
        "org",
        "collections_agent",
        "api",
        {"entity_id": "inv-1"},
        user_id="u1",
        principal_roles=["tenant_admin"],
        principal_attrs={},
        source_event_type=None,
    )
    assert out is not None
    assert out.get("delegated_to_m38") is True


def test_langgraph_m38_delegate_flag() -> None:
    with patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.runtime_service") as mock_rt:
        mock_rt.schema_ready.return_value = True
        mock_rt.chat.return_value = MagicMock(
            status="completed",
            goal_run_id="r1",
            model_dump=lambda: {},
            plan=None,
        )
        from app.services.langgraph_runner import run_langgraph_flow

        result = run_langgraph_flow(
            "org",
            "collections_agent",
            "api",
            {"use_m38_runtime": True, "user_message": "List overdue"},
        )
        assert result.get("graph_runtime", {}).get("delegated_to") == "m38"


def test_copilot_response_has_progress_fields() -> None:
    from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import CopilotChatResponse

    resp = CopilotChatResponse(
        goal_id="g1",
        goal_run_id="r1",
        status="executing",
        assistant_message="Working",
        mode="executing",
        progress_percent=33.3,
        pending_approval_nodes=["step_2"],
        rollback_chain=[{"node_id": "step_1", "compensation": "procurement.cancel_po"}],
    )
    assert resp.progress_percent == 33.3
    assert resp.pending_approval_nodes == ["step_2"]
