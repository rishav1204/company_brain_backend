from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate import (
    evaluate_session_action,
    evaluate_tool_invocation,
)
from app.modules.finance_os.platform_ai_runtime.runtime_router import should_use_m38_runtime


def test_unified_copilot_enabled_by_default() -> None:
    from app.core.config import settings

    assert settings.m38_unified_copilot is True


def test_m38_default_runtime_enabled_by_default() -> None:
    from app.core.config import settings

    assert settings.m38_default_runtime is True


def test_should_use_m38_runtime_default() -> None:
    assert should_use_m38_runtime({}) is True


def test_should_use_m38_runtime_legacy_opt_out() -> None:
    assert should_use_m38_runtime({"use_legacy_langgraph": True}) is False


def test_unified_policy_blocks_forbidden_journal() -> None:
    decision = evaluate_tool_invocation(
        "org-1",
        tool="journal",
        method="post",
        params={},
        actor_id="u1",
        roles=["tenant_admin"],
    )
    assert decision.allowed is False
    assert decision.code == "FORBIDDEN_ACTION"
    assert is_forbidden_action("journal", "post")


@patch("app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_access")
@patch("app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate._governance_evaluate")
def test_langgraph_and_m38_share_policy_gate(mock_gov, mock_abac) -> None:
    from app.services.langgraph_runner import GraphRuntimeState, _policy_gate_node

    mock_abac.return_value = MagicMock(allowed=True, reason=None, checks=[])
    mock_gov.return_value = MagicMock(allowed=True)

    state = GraphRuntimeState(
        run_id="r1",
        graph_name="test",
        org_id="org-1",
        agent_type="collections_agent",
        trigger_type="api",
        payload={"action": "notify_user", "human_approved": True},
        principal_roles=["tenant_admin"],
        principal_attrs={"user_id": "u1"},
        proposed_actions=[],
    )
    _policy_gate_node(state)
    assert state.status == "running"
    assert any(cp.node == "policy_gate" and cp.status == "allowed" for cp in state.checkpoints)


@patch("app.modules.finance_os.platform_ai_runtime.services.runtime_service.runtime_service")
def test_langgraph_defaults_to_m38(mock_rt) -> None:
    mock_rt.schema_ready.return_value = True
    mock_resp = MagicMock(
        status="completed",
        goal_run_id="run-1",
        goal_id="g1",
        mode="completed",
        progress_percent=100.0,
    )
    mock_resp.model_dump.return_value = {"status": "completed", "goal_run_id": "run-1"}
    mock_rt.chat.return_value = mock_resp

    from app.services.langgraph_runner import run_langgraph_flow

    result = run_langgraph_flow(
        "org-1",
        "collections_agent",
        "api",
        {"user_message": "List overdue invoices"},
    )
    assert result.get("graph_runtime", {}).get("delegated_to") == "m38"
    mock_rt.chat.assert_called_once()


@patch("app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline.delegate_to_m38_runtime")
def test_m29_pipeline_routes_to_m38_first(mock_delegate) -> None:
    from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline

    mock_delegate.return_value = {
        "status": "completed",
        "delegated_to_m38": True,
        "graph_runtime": {"goal_run_id": "run-1", "goal_id": "g1", "mode": "completed", "progress_percent": 100},
        "m38": {"status": "completed", "plan": {"confidence": 90, "confidence_band": "strong"}},
    }
    out = agent_orchestration_pipeline._run_inner(
        "org-1",
        "collections_agent",
        "api",
        {"user_message": "List overdue"},
        user_id="u1",
        principal_roles=["tenant_admin"],
        principal_attrs={},
    )
    assert out.get("delegated_to_m38") is True
    mock_delegate.assert_called_once()


def test_context_bridge_returns_text_when_unified_copilot_on() -> None:
    with patch("app.modules.finance_os.platform_ai_runtime.context.context_bridge.platform_context_engine") as mock_pce:
        mock_pce.build.return_value = MagicMock(summaries={"ap": "summary"})
        with patch("app.modules.finance_os.platform_ai_runtime.context.context_bridge.prompt_assembler") as mock_pa:
            mock_pa.build_planner_context_block.return_value = "unified context block"
            from app.modules.finance_os.platform_ai_runtime.context.context_bridge import build_unified_context

            text = build_unified_context("org-1", "What is overdue AR?", module_hint="ar")
            assert text == "unified context block"


def test_session_policy_requires_approval_flag() -> None:
    with patch("app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.evaluate_access") as mock_abac:
        with patch("app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate._governance_evaluate") as mock_gov:
            with patch("app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate.requires_human_approval") as mock_req:
                mock_abac.return_value = MagicMock(allowed=True, reason=None, checks=[])
                mock_gov.return_value = MagicMock(allowed=True)
                mock_req.return_value = True
                decision = evaluate_session_action(
                    "org-1",
                    action="payment.approve",
                    payload={"amount": 1000000},
                    actor_id="u1",
                    roles=["tenant_admin"],
                    human_approved=False,
                )
                assert decision.requires_human_approval is True
                assert decision.code == "HUMAN_APPROVAL_REQUIRED"
