"""Phase 8 Wave 2 — Runtime reliability tests (AI-02, AI-04, AI-05–AI-08)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.finance_os.platform_ai_runtime.context.entity_resolver import EntityResolver
from app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator import RetrievalOrchestrator
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import RetrievalPlan, RetrievalSource
from app.modules.finance_os.platform_ai_runtime.engine.compensation_engine import compensation_engine
from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.engine.failure_taxonomy import (
    FailureClass,
    classify_exception,
    classify_tool_result,
)
from app.modules.finance_os.platform_ai_runtime.engine.rollback_manager import rollback_manager
from app.modules.finance_os.platform_ai_runtime.events.event_listener import consume_goal_trigger
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, WorldState, WorldStateOrg, WorldStateScreen
from app.modules.finance_os.platform_ai_runtime.services.runtime_service import _recover_interrupted_nodes
from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry


# ── AI-02 Entity resolution ───────────────────────────────────────────────


def test_entity_resolver_v2_exact_ui_context_high_confidence() -> None:
    resolver = EntityResolver()
    ws = WorldState(
        screen=WorldStateScreen(entity_type="vendor", entity_id="v-1"),
        org=WorldStateOrg(company_id="c1", branch_id="b1", fiscal_period_id="p1"),
        selection={"vendor_id": "v-1"},
    )
    result = resolver.resolve_v2("show me this vendor balance", world_state=ws, org_id="org-1")
    assert result.entities
    top = result.entities[0]
    assert top.entity_type == "vendor"
    assert top.entity_id == "v-1"
    assert top.confidence >= 0.75
    assert top.needs_clarification is False


def test_entity_resolver_never_guesses_below_threshold(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "m38_entity_confidence_threshold", 0.99)
    monkeypatch.setattr(config_mod.settings, "m38_entity_min_margin", 0.05)
    resolver = EntityResolver()
    result = resolver.resolve_v2("pay acme something vague", world_state=WorldState(), org_id="org-1")
    for ent in result.entities:
        if ent.entity_id:
            assert ent.confidence >= 0.99 or ent.needs_clarification
        else:
            assert ent.needs_clarification or not ent.entity_id
    # No auto-bind of entity_id when ambiguous/low confidence
    bound_without_clarification = [
        e for e in result.entities if e.entity_id and not e.needs_clarification and e.confidence < 0.99
    ]
    assert bound_without_clarification == []


def test_entity_resolver_alias_match() -> None:
    resolver = EntityResolver()
    result = resolver.resolve_v2("what do we owe supplier Acme", world_state=WorldState(), org_id="org-1")
    assert any(c.entity_type == "vendor" for c in result.candidates) or any(
        e.entity_type == "vendor" for e in result.entities
    )


# ── AI-04 Retrieval reliability ───────────────────────────────────────────


def test_retrieval_orchestrator_records_failure_and_retries(monkeypatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "m38_retrieval_max_retries", 2)
    monkeypatch.setattr(config_mod.settings, "m38_retrieval_retry_base_ms", 1)
    orch = RetrievalOrchestrator()
    plan = RetrievalPlan(
        query="cash position",
        sources=[RetrievalSource(source_type="memory", tool="memory", method="search", priority=1)],
    )
    call_count = {"n": 0}

    def flaky_search(*args, **kwargs):
        call_count["n"] += 1
        raise RuntimeError("vector store timeout")

    with patch(
        "app.modules.finance_os.agents.bridges.m27_bridge.search",
        side_effect=flaky_search,
    ):
        with patch("app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.log_event") as mock_log:
            out = orch.fetch("org-1", plan=plan, world_state=WorldState(), entities=[], goal_id="g1")

    assert out["retrieval_complete"] is False
    assert out.get("retrieval_failures")
    assert call_count["n"] >= 3  # initial + 2 retries
    assert any(c.args and c.args[0] == "m38.context.retrieval_failed" for c in mock_log.call_args_list)
    assert out.get("planner_hints", {}).get("partial_context") is True


def test_retrieval_does_not_swallow_planner_hints() -> None:
    orch = RetrievalOrchestrator()
    plan = RetrievalPlan(
        query="x",
        sources=[RetrievalSource(source_type="documents", tool="documents", method="search")],
    )
    with patch(
        "app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.retrieve_context",
        side_effect=RuntimeError("pg down"),
    ):
        with patch("app.modules.finance_os.platform_ai_runtime.context.retrieval_orchestrator.log_event"):
            out = orch.fetch("org-1", plan=plan, world_state=WorldState(), entities=[])
    assert "retrieval_failures" in out
    assert isinstance(out["retrieval_failures"], list)
    assert len(out["retrieval_failures"]) >= 1
    assert out.get("planner_hints") is not None


# ── AI-05 Compensation ────────────────────────────────────────────────────


def test_compensation_registry_wired_for_draft_tools() -> None:
    assert tool_registry.compensation_for("procurement", "create_po") == "procurement.cancel_po"
    assert tool_registry.compensation_for("procurement", "create_grn") == "procurement.cancel_grn"
    assert tool_registry.compensation_for("journals", "create_draft") == "journals.void_draft"
    assert tool_registry.compensation_for("ap", "create_invoice") == "ap.cancel_invoice"
    assert tool_registry.compensation_for("inventory", "create_item") == "inventory.deactivate_item"
    # Confirm GRN is irreversible via cancel
    assert compensation_engine.is_reversible("procurement", "confirm_grn") is False
    assert ("procurement", "cancel_grn") in {(t["tool"], t["method"]) for t in tool_registry.list_tools()}
    assert ("journals", "void_draft") in {(t["tool"], t["method"]) for t in tool_registry.list_tools()}


def test_attach_missing_compensations() -> None:
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(id="n1", tool="procurement", method="create_po", params={}, status="pending"),
            GraphNodeSpec(id="n2", tool="procurement", method="submit_po", params={}, status="pending"),
        ]
    )
    compensation_engine.attach_missing_compensations(graph)
    assert graph.nodes["n1"].compensation_tool == "procurement.cancel_po"


def test_build_undo_graph_requires_approval() -> None:
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(
                id="n1",
                tool="procurement",
                method="create_po",
                params={"po_id": "p1"},
                status="completed",
                compensation_tool="procurement.cancel_po",
            )
        ]
    )
    undo = rollback_manager.build_undo_graph(graph, steps=1)
    assert len(undo.nodes) == 1
    undo_node = next(iter(undo.nodes.values()))
    assert undo_node.requires_approval is True
    assert undo_node.method in {"cancel_po", "cancel"}


# ── AI-06 Forensics optional ───────────────────────────────────────────────


def test_forensics_failure_does_not_block_undo() -> None:
    with patch(
        "app.modules.platform.governance.services.forensics_service.forensics_service"
    ) as mock_f:
        mock_f.rollback_analysis.side_effect = RuntimeError("forensics down")
        ctx = rollback_manager.forensics_context("org-1", entity_type="procurement", entity_id="x")
    assert ctx["available"] is False
    assert ctx.get("advisory_only") is True
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(
                id="n1",
                tool="procurement",
                method="create_po",
                params={"po_id": "p1"},
                status="completed",
                compensation_tool="procurement.cancel_po",
            )
        ]
    )
    undo = rollback_manager.build_undo_graph(graph)
    chain = rollback_manager.enrich_undo_plan("org-1", graph, undo)
    assert chain
    assert len(undo.nodes) == 1


# ── AI-07 Long-running / resume ───────────────────────────────────────────


def test_max_runtime_steps_from_settings() -> None:
    from app.core.config import settings
    from app.modules.finance_os.platform_ai_runtime.services.runtime_service import _max_steps

    assert _max_steps() == int(settings.m38_max_runtime_steps)
    assert settings.m38_max_runtime_steps >= 50


def test_recover_interrupted_nodes_only_resets_running() -> None:
    graph = ExecutionGraph(
        nodes=[
            GraphNodeSpec(id="a", tool="x", method="y", status="completed"),
            GraphNodeSpec(id="b", tool="x", method="y", status="running"),
            GraphNodeSpec(id="c", tool="x", method="y", status="pending"),
        ]
    )
    n = _recover_interrupted_nodes(graph)
    assert n == 1
    assert graph.nodes["a"].status == "completed"
    assert graph.nodes["b"].status == "pending"
    assert graph.nodes["c"].status == "pending"
    # next_ready should skip completed
    ready = graph.next_ready_node()
    assert ready is not None
    assert ready.id in {"b", "c"}


# ── AI-08 Event reliability ───────────────────────────────────────────────


def test_goal_trigger_logs_and_reraises_on_failure() -> None:
    envelope = {
        "event_type": "invoice.overdue",
        "org_id": "org-1",
        "correlation_id": "corr-1",
        "causation_id": "cause-1",
        "retry_count": 0,
        "payload": {"goal_id": "g1", "execution_id": "e1"},
    }
    with patch(
        "app.modules.finance_os.platform_ai_runtime.events.event_listener.GOAL_TRIGGER_MAP",
        {"invoice.overdue": "collections"},
    ):
        with patch(
            "app.modules.finance_os.platform_ai_runtime.events.event_listener.goal_manager"
        ) as mock_gm:
            with patch(
                "app.modules.platform.billing.billing_hooks.gate_ai_event",
                return_value=True,
            ):
                mock_gm.handle_event.side_effect = RuntimeError("db down")
                with patch("app.modules.finance_os.platform_ai_runtime.events.event_listener.log_event") as mock_log:
                    with pytest.raises(RuntimeError, match="db down"):
                        consume_goal_trigger(envelope)
                    assert any(
                        c.args and c.args[0] == "m38.event.goal_trigger_failed" for c in mock_log.call_args_list
                    )


def test_event_meta_includes_required_fields() -> None:
    from app.modules.finance_os.platform_ai_runtime.events.event_listener import _envelope_meta

    meta = _envelope_meta(
        {
            "event_type": "x",
            "org_id": "o1",
            "correlation_id": "c",
            "causation_id": "z",
            "retry_count": 2,
            "payload": {"execution_id": "e", "goal_id": "g"},
        }
    )
    for key in (
        "correlation_id",
        "causation_id",
        "execution_id",
        "goal_id",
        "organization_id",
        "timestamp",
        "retry_count",
    ):
        assert key in meta
    assert meta["retry_count"] == 2
    assert meta["organization_id"] == "o1"


# ── Failure taxonomy ──────────────────────────────────────────────────────


def test_failure_taxonomy_classifies_timeout_retryable() -> None:
    cf = classify_tool_result(
        {"status": "error", "detail": "connection timed out"},
        node_id="n1",
        tool="ap",
        method="list",
    )
    assert cf is not None
    assert cf.failure_class == FailureClass.TIMEOUT
    assert cf.retryable is True


def test_failure_taxonomy_policy() -> None:
    cf = classify_tool_result(
        {"status": "error", "detail": "policy denied", "policy_code": "POLICY_DENIED"},
        tool="journals",
        method="create_draft",
    )
    assert cf is not None
    assert cf.failure_class == FailureClass.POLICY
    assert cf.retryable is False


def test_classify_exception_context() -> None:
    cf = classify_exception(TimeoutError("timeout"), context="retrieval")
    assert cf.failure_class == FailureClass.TIMEOUT
    assert cf.retryable is True


# ── Config knobs ───────────────────────────────────────────────────────────


def test_wave2_config_knobs_present() -> None:
    from app.core.config import settings

    assert hasattr(settings, "m38_entity_confidence_threshold")
    assert hasattr(settings, "m38_entity_min_margin")
    assert hasattr(settings, "m38_max_runtime_steps")
    assert hasattr(settings, "m38_retrieval_max_retries")
    assert hasattr(settings, "m38_event_max_retries")
    assert hasattr(settings, "m38_step_max_auto_retries")
    assert settings.m38_entity_confidence_threshold > 0
