from __future__ import annotations

from app.modules.finance_os.agents.orchestrator.forbidden_actions import FORBIDDEN_TOOLS, is_forbidden_action, filter_actions
from app.modules.finance_os.agents.orchestrator.agent_registry import AGENT_REGISTRY, AGENT_CATALOG, get_agent
from app.modules.finance_os.agents.orchestrator.task_router import EVENT_AGENT_MAP, resolve_agent, task_type_for
from app.modules.finance_os.agents.engine.confidence_engine import score
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan, ConfidenceResult
from app.modules.finance_os.agents.agents.ap_agent import ApAgent
from app.modules.finance_os.agents.agents.reconciliation_agent import ReconciliationAgent
from app.modules.finance_os.agents.agents.gst_agent import GstAgent
from app.modules.finance_os.agents.agents.close_agent import CloseAgent
from app.modules.finance_os.agents.agents.collections_agent import CollectionsAgent
from app.modules.finance_os.agents.agents.treasury_agent import TreasuryAgent
from app.modules.finance_os.agents.ai.policy_reasoner import check as check_policy
from app.modules.finance_os.agents.orchestrator.execution_planner import enrich_payload, plan_to_payload_actions
from app.modules.finance_os.agents.orchestrator.workflow_launcher import WORKFLOW_MAP
from app.modules.finance_os.agents.events.agents_events import (
    AGENT_STARTED,
    AGENT_COMPLETED,
    AGENT_RECOMMENDATION_CREATED,
    AGENT_WORKFLOW_CREATED,
)
from app.services.langgraph_runner import _normalize_agent_key, ToolAction
from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import is_finance_os_agent, FINANCE_OS_AGENTS


def _ctx(**kwargs) -> AgentContext:
    return AgentContext(org_id="org-1", agent_name="ap_agent", **kwargs)


def test_forbidden_journal_tool() -> None:
    assert is_forbidden_action("journal", "post") is True


def test_forbidden_payment_execute() -> None:
    assert is_forbidden_action("payment", "executePayment") is True


def test_forbidden_gst_filing() -> None:
    assert is_forbidden_action("gst", "file") is True


def test_forbidden_erp_writeback() -> None:
    assert is_forbidden_action("erp", "writeback") is True


def test_allowed_email_send() -> None:
    assert is_forbidden_action("email", "send") is False


def test_allowed_memory_search() -> None:
    assert is_forbidden_action("memory", "search") is False


def test_allowed_graph_traverse() -> None:
    assert is_forbidden_action("graph", "traverse") is False


def test_allowed_workflow_update() -> None:
    assert is_forbidden_action("workflow", "updateStatus") is False


def test_forbidden_tools_set_includes_journal() -> None:
    assert "journal" in FORBIDDEN_TOOLS


def test_filter_actions_blocks_journal() -> None:
    actions = [ToolAction(tool="journal", method="post", params={}), ToolAction(tool="email", method="send", params={})]
    allowed, blocked = filter_actions(actions)
    assert len(allowed) == 1
    assert "journal.post" in blocked


def test_filter_actions_all_allowed() -> None:
    actions = [ToolAction(tool="slack", method="postMessage", params={})]
    allowed, blocked = filter_actions(actions)
    assert len(allowed) == 1
    assert blocked == []


def test_agent_registry_has_ap_agent() -> None:
    assert "ap_agent" in AGENT_REGISTRY


def test_agent_registry_has_reconciliation_agent() -> None:
    assert "reconciliation_agent" in AGENT_REGISTRY


def test_agent_registry_has_gst_agent() -> None:
    assert "gst_agent" in AGENT_REGISTRY


def test_agent_registry_has_close_agent() -> None:
    assert "close_agent" in AGENT_REGISTRY


def test_agent_registry_has_collections_agent() -> None:
    assert "collections_agent" in AGENT_REGISTRY


def test_agent_registry_has_treasury_agent() -> None:
    assert "treasury_agent" in AGENT_REGISTRY


def test_catalog_has_six_agents() -> None:
    assert len(AGENT_CATALOG) == 6


def test_get_agent_ap() -> None:
    agent = get_agent("ap_agent")
    assert isinstance(agent, ApAgent)


def test_get_agent_unknown_raises() -> None:
    try:
        get_agent("unknown_agent_xyz")
        assert False
    except ValueError:
        pass


def test_resolve_agent_alias_ap_exception() -> None:
    assert resolve_agent("ap_exception_agent", {}) == "ap_agent"


def test_resolve_agent_alias_close() -> None:
    assert resolve_agent("close_orchestration_agent", {}) == "close_agent"


def test_resolve_agent_alias_treasury() -> None:
    assert resolve_agent("cashflow_risk_agent", {}) == "treasury_agent"


def test_event_map_invoice_anomaly() -> None:
    assert EVENT_AGENT_MAP["invoice.anomaly_detected"] == "ap_agent"


def test_event_map_reconciliation_exception() -> None:
    assert EVENT_AGENT_MAP["reconciliation.exception.created"] == "reconciliation_agent"


def test_event_map_gst_mismatch() -> None:
    assert EVENT_AGENT_MAP["gst.mismatch.detected"] == "gst_agent"


def test_event_map_period_close() -> None:
    assert EVENT_AGENT_MAP["erp.period.close.requested"] == "close_agent"


def test_event_map_collections() -> None:
    assert EVENT_AGENT_MAP["invoice.due"] == "collections_agent"


def test_event_map_liquidity() -> None:
    assert EVENT_AGENT_MAP["liquidity_alert.created"] == "treasury_agent"


def test_task_type_ap_default() -> None:
    assert task_type_for("ap_agent", {}) == "invoice_review"


def test_task_type_override() -> None:
    assert task_type_for("ap_agent", {"task_type": "custom"}) == "custom"


def test_ap_agent_plan_has_workflow_key() -> None:
    plan = ApAgent().plan(_ctx(entity_id="inv-1"))
    assert plan is not None
    assert plan.workflow_key == "AP_INVOICE_APPROVAL"


def test_reconciliation_agent_plan() -> None:
    plan = ReconciliationAgent().plan(_ctx(entity_id="bank-1"))
    assert plan.recommendation_type == "exception_raise"


def test_gst_agent_plan_forbids_filing() -> None:
    plan = GstAgent().plan(_ctx(entity_id="ret-1"))
    assert plan.metadata.get("filing_forbidden") is True


def test_close_agent_plan() -> None:
    plan = CloseAgent().plan(_ctx(entity_id="2024-04"))
    assert plan.workflow_key == "PERIOD_CLOSE"


def test_collections_agent_plan() -> None:
    plan = CollectionsAgent().plan(_ctx(entity_id="inv-9"))
    assert plan.recommendation_type == "collection_action"


def test_treasury_agent_advisory() -> None:
    plan = TreasuryAgent().plan(_ctx())
    assert plan.metadata.get("advisory_only") is True


def test_confidence_score_range() -> None:
    result = score(_ctx(data_quality_score=0.8, memory_snippets=[{}] * 3, graph_paths=[{}]))
    assert 0 <= result.score <= 100


def test_confidence_band_very_strong() -> None:
    result = score(_ctx(data_quality_score=1.0, memory_snippets=[{}] * 5, graph_paths=[{}] * 3))
    assert result.band in {"very_strong", "strong"}


def test_confidence_band_manual_low_data() -> None:
    result = score(_ctx(data_quality_score=0.1))
    assert result.band in {"manual", "review"}


def test_confidence_approval_high_amount() -> None:
    result = score(_ctx(raw_payload={"amount": 600000}))
    assert result.approval_required is True


def test_confidence_approval_vendor_risk() -> None:
    result = score(_ctx(raw_payload={"vendor_risk": "high"}))
    assert result.approval_required is True


def test_policy_reasoner_high_amount() -> None:
    flags = check_policy({"amount": 600000})
    assert "high_amount" in flags


def test_policy_reasoner_vendor_risk() -> None:
    flags = check_policy({"vendor_risk": "critical"})
    assert "vendor_risk" in flags


def test_policy_reasoner_gst_filing_blocked() -> None:
    flags = check_policy({"gst_filing_requested": True})
    assert "gst_filing_blocked" in flags


def test_enrich_payload_includes_context() -> None:
    ctx = _ctx(entity_id="x1")
    plan = ApAgent().plan(ctx)
    payload = enrich_payload(ctx, plan)
    assert "agent_context" in payload
    assert "agent_plan" in payload


def test_plan_to_payload_actions() -> None:
    plan = ApAgent().plan(_ctx())
    assert len(plan_to_payload_actions(plan)) >= 1


def test_normalize_agent_key_ap_alias() -> None:
    assert _normalize_agent_key("ap_exception_agent") == "ap_agent"


def test_normalize_agent_key_close_alias() -> None:
    assert _normalize_agent_key("close_orchestration_agent") == "close_agent"


def test_normalize_agent_key_reconciliation() -> None:
    assert _normalize_agent_key("reconciliation_agent") == "reconciliation_agent"


def test_normalize_agent_key_gst() -> None:
    assert _normalize_agent_key("gst_agent") == "gst_agent"


def test_normalize_agent_key_collections() -> None:
    assert _normalize_agent_key("collections_agent") == "collections_agent"


def test_is_finance_os_agent_ap() -> None:
    assert is_finance_os_agent("ap_agent") is True


def test_is_finance_os_agent_legacy() -> None:
    assert is_finance_os_agent("ap_exception_agent") is True


def test_is_finance_os_agent_unknown() -> None:
    assert is_finance_os_agent("random_copilot") is False


def test_finance_os_agents_set_size() -> None:
    assert len(FINANCE_OS_AGENTS) >= 6


def test_workflow_map_has_ap() -> None:
    assert WORKFLOW_MAP["workflow_launch"] == "AP_INVOICE_APPROVAL"


def test_agent_events_constants() -> None:
    assert AGENT_STARTED == "agent.started"
    assert AGENT_COMPLETED == "agent.completed"
    assert AGENT_RECOMMENDATION_CREATED == "agent.recommendation.created"
    assert AGENT_WORKFLOW_CREATED == "agent.workflow.created"


def test_ap_plan_proposed_actions_safe() -> None:
    plan = ApAgent().plan(_ctx())
    for action in plan.proposed_actions:
        assert is_forbidden_action(action["tool"], action["method"]) is False


def test_gst_plan_no_forbidden_actions() -> None:
    plan = GstAgent().plan(_ctx())
    for action in plan.proposed_actions:
        assert is_forbidden_action(action["tool"], action["method"]) is False


def test_close_plan_actions_safe() -> None:
    plan = CloseAgent().plan(_ctx())
    for action in plan.proposed_actions:
        assert is_forbidden_action(action["tool"], action["method"]) is False
