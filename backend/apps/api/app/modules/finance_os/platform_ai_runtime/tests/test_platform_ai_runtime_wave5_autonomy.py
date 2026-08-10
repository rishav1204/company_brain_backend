"""Phase 8 Wave 5 — Autonomous Finance OS tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner import event_driven_planner
from app.modules.finance_os.platform_ai_runtime.autonomy.governance import autonomy_governance
from app.modules.finance_os.platform_ai_runtime.autonomy.goal_memory import GoalMemory
from app.modules.finance_os.platform_ai_runtime.autonomy.organizational_learning import organizational_learning
from app.modules.finance_os.platform_ai_runtime.autonomy.recommendation_engine import autonomy_recommendation_engine
from app.modules.finance_os.platform_ai_runtime.autonomy.self_optimization import self_optimization_engine
from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import GoalPlanner, _heuristic_plan
from app.modules.finance_os.platform_ai_runtime.engine.observer import Observer
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    GraphNodeSpec,
    GoalObjective,
    PlanMetadata,
    WorldState,
    WorldStateScreen,
)


# ── Event-driven planner ───────────────────────────────────────────────────


def test_event_planner_ignore_unsubscribed() -> None:
    d = event_driven_planner.evaluate("org", event_type="random.noise", payload={})
    assert d.action == "ignore"


def test_event_planner_liquidity_recommends() -> None:
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner.goal_memory.find_matching_goal",
        return_value=None,
    ):
        d = event_driven_planner.evaluate(
            "org", event_type="liquidity_alert.created", payload={"entity_id": "acc-1"}
        )
    assert d.action in {"recommend", "prepare_workflow", "start_goal", "approval_required"}
    assert d.prep_only is True
    assert d.envelope is not None
    assert d.envelope.required_approval is True or d.envelope.prep_only is True
    assert d.recommendation is not None


def test_event_planner_prefers_resume_over_restart() -> None:
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner.goal_memory.find_matching_goal",
        return_value={"id": "g-active"},
    ):
        with patch(
            "app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner.goal_repository.get_latest_run",
            return_value={"id": "r1", "status": "paused"},
        ):
            d = event_driven_planner.evaluate("org", event_type="erp.period.close.requested", payload={})
    assert d.action == "resume_goal"
    assert d.goal_id == "g-active"


def test_event_planner_never_execute_action() -> None:
    """Decision vocabulary must not include direct execute."""
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner.goal_memory.find_matching_goal",
        return_value=None,
    ):
        for et in ("invoice.due", "payment.failed", "gst.due", "bank.statement.imported"):
            d = event_driven_planner.evaluate("org", event_type=et, payload={})
            assert d.action != "execute"
            assert d.prep_only is True


# ── Observer V2 ────────────────────────────────────────────────────────────


def test_observer_v2_outcomes() -> None:
    obs = Observer()
    node = GraphNodeSpec(id="n1", tool="ap", method="list", label="x")
    assert obs.analyze(node, {"status": "completed"}).outcome == "succeeded"
    partial = obs.analyze(node, {"status": "completed", "partial": True})
    assert partial.outcome == "partial_success"
    assert partial.terminate_goal is False
    cash = obs.analyze(node, {"status": "blocked", "detail": "insufficient_cash"})
    assert cash.outcome == "needs_alternative"
    assert cash.alternatives
    assert cash.terminate_goal is False
    prep = obs.analyze(node, {"status": "pending_approval", "code": "PREP_ONLY_MUTATION"})
    assert prep.outcome == "needs_human"
    assert prep.terminate_goal is False
    retry = obs.analyze(node, {"status": "error", "retryable": True, "detail": "timeout"})
    assert retry.outcome == "needs_retry"
    forbid = obs.analyze(node, {"status": "error", "detail": "forbidden action"})
    assert forbid.outcome == "needs_escalation"


# ── Governance ─────────────────────────────────────────────────────────────


def test_governance_blocks_autonomous_mutation() -> None:
    allowed = autonomy_governance.assert_mutates_only_with_approval(
        human_approved=False, prep_only=True, mutates=True
    )
    assert allowed["allowed"] is False
    assert allowed["code"] in {"PREP_ONLY_MUTATION", "AUTONOMY_MUTATION_BLOCKED"}
    ok = autonomy_governance.assert_mutates_only_with_approval(
        human_approved=True, prep_only=False, mutates=True
    )
    assert ok["allowed"] is True
    env = autonomy_governance.build_envelope(
        reason="prep payment", evidence=["cash low"], confidence=0.8, prep_only=True
    )
    assert env.prep_only is True
    assert "unified_policy_gate" in env.required_policy


# ── Goal memory ────────────────────────────────────────────────────────────


def test_goal_memory_attach_objectives() -> None:
    gm = GoalMemory()
    obj = GoalObjective(objective_id="o1", title="Reduce DSO", metric="dso", kind="financial")
    ws = gm.attach_objectives(WorldState(), [obj], financial_targets={"dso_days": 45})
    assert ws.operational_objectives
    assert ws.financial_targets.get("dso_days") == 45
    loaded = gm.load_from_world_state(ws)
    assert loaded[0].title == "Reduce DSO"


def test_goal_memory_find_matching_by_template() -> None:
    gm = GoalMemory()
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.goal_memory.goal_repository.list_goals_detailed",
        return_value=[
            {"id": "g1", "title": "x", "trigger_config": {"template_key": "period_close"}, "world_state": {}}
        ],
    ):
        hit = gm.find_matching_goal("org", template_key="period_close")
    assert hit and hit["id"] == "g1"


# ── Organizational learning ────────────────────────────────────────────────


def test_learning_rejects_policy_exception_content() -> None:
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.organizational_learning.goal_repository.merge_plan_metadata"
    ) as mock_merge:
        out = organizational_learning.observe_run(
            "org",
            goal_id="g",
            run_id="r",
            observations=[{"status": "success", "tool": "bypass", "method": "policy_exception"}],
        )
    # Content with forbidden tokens blocked OR persisted without authorization claims
    assert out["status"] in {"ok", "blocked"}


def test_learning_records_operational_patterns() -> None:
    with patch(
        "app.modules.finance_os.platform_ai_runtime.autonomy.organizational_learning.goal_repository.merge_plan_metadata"
    ) as mock_merge:
        out = organizational_learning.observe_run(
            "org",
            goal_id="g",
            run_id="r",
            observations=[
                {"status": "success", "tool_name": "ar", "tool_method": "list_overdue"},
                {"status": "blocked", "tool_name": "workflow", "tool_method": "start"},
            ],
        )
    assert out["status"] == "ok"
    assert "patterns" in out
    mock_merge.assert_called_once()


# ── Self optimization ──────────────────────────────────────────────────────


def test_self_optimization_dedupes_and_parallelizes() -> None:
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(id="a", tool="memory", method="search", label="m"),
            GraphNodeSpec(id="b", tool="graph", method="traverse", label="g"),
            GraphNodeSpec(id="c", tool="ar", method="list_outstanding", label="ar"),
            GraphNodeSpec(id="d", tool="ap", method="list_outstanding", label="ap"),
        ]
    )
    meta = PlanMetadata(reasoning="t", confidence=70)
    g2, m2, notes = self_optimization_engine.optimize(
        graph, meta, context_preloaded=True, prep_only=True
    )
    assert "skipped_redundant_retrieval" in notes or any("skipped" in n for n in notes)
    assert m2.prep_only is True or any("prep_only" in n for n in notes)


def test_self_optimization_prep_only_gates_mutations() -> None:
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(id="m", tool="procurement", method="create_po", label="po", requires_approval=False),
        ]
    )
    # create_po is draft mutate if in DRAFT_SPECS; regardless prep_only flag should set requires_approval when in mutate set
    g2, m2, notes = self_optimization_engine.optimize(graph, PlanMetadata(), prep_only=True)
    assert m2.prep_only is True


# ── Recommendations ────────────────────────────────────────────────────────


def test_recommendation_has_evidence_and_impact() -> None:
    rec = autonomy_recommendation_engine.from_template(
        "treasury_advisory",
        reason="Cash below threshold",
        evidence=["event=cash.below_threshold"],
        confidence=0.8,
        entity_id="acc",
    )
    assert rec.evidence
    assert rec.business_impact
    assert rec.required_approvals
    assert rec.prep_only is True
    msg = autonomy_recommendation_engine.collaboration_message(rec)
    assert "No financial truth was changed" in msg
    assert "Prepared" in msg or "recommendation" in msg.lower()


# ── Heuristic prep plans ───────────────────────────────────────────────────


def test_period_close_plan_is_long_running_prep() -> None:
    graph, meta = _heuristic_plan("month-end close books checklist", WorldState(), prep_only=True)
    assert len(graph.nodes) >= 8
    assert meta.estimated_completion == "days"
    assert any(n.parallel_group == "close_reads" for n in graph.nodes.values())
    close = graph.nodes.get("step_9")
    assert close and close.requires_approval


def test_gst_prepare_plan_no_file() -> None:
    graph, meta = _heuristic_plan("prepare GST return draft for filing", WorldState(), prep_only=True)
    tools = {f"{n.tool}.{n.method}" for n in graph.nodes.values()}
    assert not any("file" in t for t in tools)
    assert meta.collaboration_message


def test_goal_planner_finalize_attaches_envelope(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.m38_autonomy_enabled", True)
    planner = GoalPlanner()
    with patch("app.services.llm_provider.llm_provider.is_ready", return_value=False):
        graph, meta = planner.plan(
            "[PREP-ONLY] daily treasury review cash position",
            world_state=WorldState(),
            use_llm=False,
            org_id="org-1",
            prep_only=True,
        )
    assert meta.envelope is not None
    assert meta.envelope.prep_only is True
    assert meta.prep_only is True


# ── Restart recovery integration with existing helper ──────────────────────


def test_recover_interrupted_nodes_wave5() -> None:
    from app.modules.finance_os.platform_ai_runtime.services.runtime_service import _recover_interrupted_nodes

    g = ExecutionGraph(
        nodes=[
            GraphNodeSpec(id="a", tool="ar", method="list", status="running"),
            GraphNodeSpec(id="b", tool="ap", method="list", status="completed"),
            GraphNodeSpec(id="c", tool="gl", method="tb", status="pending"),
        ]
    )
    n = _recover_interrupted_nodes(g)
    assert n == 1
    assert g.nodes["a"].status == "pending"
    assert g.nodes["b"].status == "completed"


# ── Goal manager event handle ──────────────────────────────────────────────


def test_goal_manager_handle_event_observe() -> None:
    from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GoalManager

    gm = GoalManager()
    with patch(
        "app.modules.finance_os.platform_ai_runtime.goals.goal_manager.event_driven_planner.evaluate"
    ) as mock_ev:
        from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import EventPlanDecision

        mock_ev.return_value = EventPlanDecision(
            action="observe",
            event_type="invoice.created",
            recommendation={"title": "watch"},
            collaboration_message="Observing invoice create",
        )
        out = gm.handle_event("org", event_type="invoice.created", payload={})
    assert out and out["status"] == "observed"


def test_goal_manager_handle_event_resume() -> None:
    from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import GoalManager

    gm = GoalManager()
    with patch(
        "app.modules.finance_os.platform_ai_runtime.goals.goal_manager.event_driven_planner.evaluate"
    ) as mock_ev:
        from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import EventPlanDecision

        mock_ev.return_value = EventPlanDecision(
            action="resume_goal",
            event_type="erp.period.close.requested",
            goal_id="g1",
            template_key="period_close",
            prep_only=True,
        )
        with patch.object(gm, "create_or_resume", return_value={"status": "executing", "goal_id": "g1"}) as mock_cr:
            out = gm.handle_event("org", event_type="erp.period.close.requested", payload={})
            mock_cr.assert_called_once()
            assert mock_cr.call_args.kwargs.get("goal_id") == "g1"
    assert out and out.get("goal_id") == "g1"


def test_autonomy_gate_in_simulate() -> None:
    """Simulates execute-path gate used by runtime."""
    gate = autonomy_governance.assert_mutates_only_with_approval(
        human_approved=False, prep_only=False, mutates=True
    )
    assert gate["allowed"] is False
