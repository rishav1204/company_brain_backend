from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.finance_os.workflow_intelligence.engine.bottleneck_engine import rank_bottlenecks, top_bottleneck
from app.modules.finance_os.workflow_intelligence.engine.optimization_engine import (
    detect_queue_overload,
    pass_through_rate,
    recommend_delegation,
    recommend_stage_removal,
    OVERLOAD_THRESHOLD,
)
from app.modules.finance_os.workflow_intelligence.engine.sla_engine import breach_risk, format_eta, predict_completion
from app.modules.finance_os.workflow_intelligence.engine.workflow_graph_engine import build_execution_graph, remaining_stages
from app.modules.finance_os.workflow_intelligence.engine.workflow_scoring_engine import (
    efficiency_score,
    health_band,
    org_health_score,
)
from app.modules.finance_os.workflow_intelligence.ai.sla_predictor import predict_sla
from app.modules.finance_os.workflow_intelligence.events.workflow_intelligence_events import (
    WORKFLOW_BOTTLENECK_DETECTED,
    WORKFLOW_HEALTH_UPDATED,
)


def _stats(p95: float, key: str = "finance") -> dict:
    return {"step_key": key, "stage_name": key, "p95_seconds": p95, "avg_seconds": p95 * 0.5, "sample_count": 10}


def test_rank_bottlenecks_orders_desc() -> None:
    ranked = rank_bottlenecks([_stats(100, "a"), _stats(500, "b"), _stats(200, "c")])
    assert ranked[0]["step_key"] == "b"
    assert ranked[0]["is_bottleneck"] is True


def test_top_bottleneck() -> None:
    top = top_bottleneck([_stats(100), _stats(900)])
    assert top is not None
    assert top["p95_seconds"] == 900


def test_rank_empty() -> None:
    assert rank_bottlenecks([]) == []


def test_efficiency_score_on_target() -> None:
    assert efficiency_score(actual_seconds=100, sla_target_seconds=100) == 0.0


def test_efficiency_score_faster() -> None:
    score = efficiency_score(actual_seconds=50, sla_target_seconds=100)
    assert score == 50.0


def test_efficiency_band_excellent() -> None:
    assert health_band(95) == "excellent"


def test_efficiency_band_good() -> None:
    assert health_band(75) == "good"


def test_efficiency_band_needs_review() -> None:
    assert health_band(55) == "needs_review"


def test_efficiency_band_poor() -> None:
    assert health_band(30) == "poor"


def test_org_health_penalty() -> None:
    base = org_health_score(efficiency_scores=[90, 85], breach_risk_count=0, overload_count=0)
    penalized = org_health_score(efficiency_scores=[90, 85], breach_risk_count=3, overload_count=2)
    assert penalized < base


def test_predict_completion() -> None:
    eta = predict_completion(remaining_stage_p95=[3600, 1800], pending_approvals=2, avg_approval_wait_seconds=600)
    assert eta == 6600


def test_breach_risk_high() -> None:
    due = datetime.utcnow() + timedelta(hours=1)
    risk, conf = breach_risk(predicted_completion_seconds=7200, due_at=due)
    assert risk == "high"
    assert conf >= 0.85


def test_breach_risk_low() -> None:
    due = datetime.utcnow() + timedelta(days=5)
    risk, _ = breach_risk(predicted_completion_seconds=3600, due_at=due)
    assert risk == "low"


def test_format_eta_minutes() -> None:
    assert "minute" in format_eta(300)


def test_format_eta_hours() -> None:
    assert "hour" in format_eta(7200)


def test_format_eta_days() -> None:
    assert "day" in format_eta(200000)


def test_build_execution_graph() -> None:
    graph = build_execution_graph(
        definition_steps=[{"key": "mgr", "name": "Manager", "type": "approval"}],
        executed_steps=[{"step_key": "mgr", "status": "completed", "started_at": "2024-01-01T10:00:00", "completed_at": "2024-01-01T12:00:00"}],
    )
    assert len(graph) == 1
    assert graph[0]["duration_seconds"] == 7200


def test_remaining_stages() -> None:
    graph = [{"step_key": "a", "status": "completed"}, {"step_key": "b", "status": "pending"}]
    assert len(remaining_stages(graph)) == 1


def test_recommend_stage_removal() -> None:
    r = recommend_stage_removal(step_key="senior_mgr", pass_through_rate=0.99, rejection_rate=0.0, avg_hours=32)
    assert r is not None
    assert r["recommendation_type"] == "remove_stage"


def test_no_stage_removal_low_ptr() -> None:
    assert recommend_stage_removal(step_key="x", pass_through_rate=0.5, rejection_rate=0.1, avg_hours=1) is None


def test_recommend_delegation() -> None:
    r = recommend_delegation(assignee_id="u1", pending_count=OVERLOAD_THRESHOLD + 10, avg_wait_hours=2)
    assert r is not None


def test_no_delegation_under_threshold() -> None:
    assert recommend_delegation(assignee_id="u1", pending_count=5, avg_wait_hours=2) is None


def test_queue_overload() -> None:
    items = detect_queue_overload({"u1": 60, "u2": 10})
    assert len(items) == 1
    assert items[0]["assignee_id"] == "u1"


def test_pass_through_rate() -> None:
    assert pass_through_rate(98, 100) == 0.98


def test_predict_sla_payload() -> None:
    result = predict_sla({"remaining_stage_p95": [3600], "pending_approvals": 0, "avg_approval_wait_seconds": 1000})
    assert "breach_risk" in result
    assert "predicted_eta" in result


def test_events_constants() -> None:
    assert WORKFLOW_BOTTLENECK_DETECTED == "workflow.bottleneck.detected"
    assert WORKFLOW_HEALTH_UPDATED == "workflow.health.updated"


def test_guard_read_workflow_perm() -> None:
    from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import require_workflow_intelligence_read

    require_workflow_intelligence_read({"permissions": ["workflow.read"]})


def test_guard_write_role() -> None:
    from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import require_workflow_intelligence_write

    require_workflow_intelligence_write({"roles": ["finance_manager"]})


def test_schema_health() -> None:
    from app.modules.finance_os.workflow_intelligence.schemas.workflow_intelligence_schema import HealthResponse

    h = HealthResponse(health_score=80, health_band="good")
    assert h.health_score == 80


def test_bottleneck_single_stage() -> None:
    ranked = rank_bottlenecks([_stats(100)])
    assert ranked[0]["is_bottleneck"] is True


def test_efficiency_clamped() -> None:
    assert efficiency_score(actual_seconds=200, sla_target_seconds=100) == 0.0


def test_org_health_empty() -> None:
    assert org_health_score(efficiency_scores=[], breach_risk_count=0, overload_count=0) == 50.0


def test_breach_risk_medium() -> None:
    due = datetime.utcnow() + timedelta(hours=3)
    risk, _ = breach_risk(predicted_completion_seconds=7200, due_at=due, buffer_seconds=3600)
    assert risk in {"medium", "high", "low"}


def test_graph_pending_step() -> None:
    graph = build_execution_graph(
        definition_steps=[{"key": "a", "name": "A"}],
        executed_steps=[{"step_key": "a", "status": "pending"}],
    )
    assert graph[0]["status"] == "pending"


def test_remaining_none_completed() -> None:
    assert remaining_stages([{"status": "completed"}, {"status": "skipped"}]) == []


def test_overload_threshold_constant() -> None:
    assert OVERLOAD_THRESHOLD == 50


def test_pass_through_zero() -> None:
    assert pass_through_rate(0, 0) == 0.0


def test_rank_three_stages() -> None:
    ranked = rank_bottlenecks([_stats(10), _stats(20), _stats(30)])
    assert len(ranked) == 3


def test_delegation_impact_score() -> None:
    r = recommend_delegation(assignee_id="u1", pending_count=100, avg_wait_hours=4)
    assert r is not None
    assert r["impact_score"] > 0


def test_stage_removal_metadata() -> None:
    r = recommend_stage_removal(step_key="cfo", pass_through_rate=0.99, rejection_rate=0, avg_hours=72)
    assert r is not None
    assert r["metadata"]["step_key"] == "cfo"


def test_sla_predict_confidence() -> None:
    r = predict_sla({"remaining_stage_p95": [], "pending_approvals": 0, "avg_approval_wait_seconds": 0})
    assert r["confidence_score"] >= 0


def test_health_band_boundary_90() -> None:
    assert health_band(91) == "excellent"


def test_health_band_boundary_70() -> None:
    assert health_band(70) == "good"


def test_health_band_boundary_50() -> None:
    assert health_band(50) == "needs_review"


def test_predict_completion_zero() -> None:
    assert predict_completion(remaining_stage_p95=[], pending_approvals=0, avg_approval_wait_seconds=0) == 0


def test_bottleneck_rank_score() -> None:
    ranked = rank_bottlenecks([_stats(250, "slow")])
    assert ranked[0]["rank_score"] == 250


def test_graph_multiple_def_steps() -> None:
    graph = build_execution_graph(
        definition_steps=[{"key": "a"}, {"key": "b"}],
        executed_steps=[],
    )
    assert len(graph) == 2


def test_queue_overload_empty() -> None:
    assert detect_queue_overload({}) == []


def test_efficiency_historical_fallback() -> None:
    score = efficiency_score(actual_seconds=100, sla_target_seconds=None, historical_p50=200)
    assert score == 50.0


def test_breach_risk_no_due() -> None:
    risk, conf = breach_risk(predicted_completion_seconds=1000, due_at=None)
    assert risk == "low"


def test_format_eta_one_hour() -> None:
    assert format_eta(3600) == "1 hours"


def test_remaining_mixed_status() -> None:
    rem = remaining_stages([{"status": "running"}, {"status": "completed"}])
    assert len(rem) == 1


def test_top_bottleneck_empty() -> None:
    assert top_bottleneck([]) is None


def test_ar_hook_pattern() -> None:
    from app.modules.workflows.services.erp_workflow_consumer import _ENTITY_WORKFLOW_MAP

    assert "sales_invoice" in _ENTITY_WORKFLOW_MAP


def test_langgraph_agent_alias() -> None:
    from app.services.langgraph_runner import _normalize_agent_key

    assert _normalize_agent_key("workflow_intelligence_copilot") == "workflow_intelligence_copilot"
