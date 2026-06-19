from datetime import date

from app.modules.erp.compliance.ai.compliance_assistant import answer_compliance_question
from app.modules.erp.compliance.ai.filing_advisor import filing_readiness_score
from app.modules.erp.compliance.ai.notice_predictor import predict_notice_risk
from app.modules.erp.compliance.ai.risk_detector import compute_risk_score, detect_risks
from app.modules.erp.compliance.engine.compliance_engine import calendar_color, priority_for_status, refresh_status
from app.modules.erp.compliance.engine.due_date_engine import compute_due_date, periods_for_generation
from app.modules.erp.compliance.engine.escalation_engine import next_escalation_level, should_escalate
from app.modules.erp.compliance.engine.penalty_engine import estimate_penalty
from app.modules.erp.compliance.engine.scheduler_engine import apply_status_refresh, generation_periods
from app.modules.erp.compliance.repositories.compliance_repository import LEGACY_TYPE_MAP
from app.modules.erp.tax.engine.compliance_engine import seed_obligations_for_period, upcoming_deadlines


def test_monthly_due_date_gstr1_rule() -> None:
    due = compute_due_date(return_period="2025-04", frequency="monthly", due_day=11, month_offset=1)
    assert due == date(2025, 5, 11)


def test_monthly_due_date_gstr3b_rule() -> None:
    due = compute_due_date(return_period="2025-04", frequency="monthly", due_day=20, month_offset=1)
    assert due == date(2025, 5, 20)


def test_tds_challan_due_day_7() -> None:
    due = compute_due_date(return_period="2025-06", frequency="monthly", due_day=7, month_offset=1)
    assert due == date(2025, 7, 7)


def test_quarterly_due_date_26q() -> None:
    due = compute_due_date(return_period="2025-03", frequency="quarterly", due_day=31, month_offset=3)
    assert due.month == 6


def test_annual_due_date_audit() -> None:
    due = compute_due_date(return_period="2025-03", frequency="annual", due_day=30, month_offset=9)
    assert due.year == 2025


def test_due_day_clamped_to_month_end() -> None:
    due = compute_due_date(return_period="2025-01", frequency="monthly", due_day=31, month_offset=1)
    assert due == date(2025, 2, 28)


def test_periods_for_generation_three_months() -> None:
    periods = periods_for_generation(year=2025, month=10, months_ahead=3)
    assert periods == ["2025-10", "2025-11", "2025-12"]


def test_periods_for_generation_year_rollover() -> None:
    periods = periods_for_generation(year=2025, month=11, months_ahead=3)
    assert periods[-1] == "2026-01"


def test_status_upcoming() -> None:
    assert refresh_status(due_date=date.today() + __import__("datetime").timedelta(days=30), status="upcoming") == "upcoming"


def test_status_due_soon() -> None:
    assert refresh_status(due_date=date.today() + __import__("datetime").timedelta(days=3), status="upcoming") == "due_soon"


def test_status_overdue() -> None:
    assert refresh_status(due_date=date.today() - __import__("datetime").timedelta(days=1), status="upcoming") == "overdue"


def test_status_completed_unchanged() -> None:
    assert refresh_status(due_date=date.today() - __import__("datetime").timedelta(days=5), status="completed") == "completed"


def test_status_waived_unchanged() -> None:
    assert refresh_status(due_date=date.today() - __import__("datetime").timedelta(days=5), status="waived") == "waived"


def test_priority_critical_for_overdue() -> None:
    assert priority_for_status("overdue") == "critical"


def test_priority_high_for_due_soon() -> None:
    assert priority_for_status("due_soon") == "high"


def test_priority_medium_for_upcoming() -> None:
    assert priority_for_status("upcoming") == "medium"


def test_calendar_color_red_overdue() -> None:
    assert calendar_color("overdue") == "red"


def test_calendar_color_orange_due_soon() -> None:
    assert calendar_color("due_soon") == "orange"


def test_calendar_color_green_completed() -> None:
    assert calendar_color("completed") == "green"


def test_escalation_level_1() -> None:
    level, role = next_escalation_level(0)
    assert level == 1
    assert role == "assignee"


def test_escalation_level_4_cfo() -> None:
    level, role = next_escalation_level(3)
    assert level == 4
    assert role == "cfo"


def test_escalation_max_level() -> None:
    level, role = next_escalation_level(4)
    assert role is None


def test_should_escalate_overdue() -> None:
    assert should_escalate(status="overdue", due_date=date.today() - __import__("datetime").timedelta(days=2), today=date.today())


def test_should_not_escalate_completed() -> None:
    assert not should_escalate(status="completed", due_date=date.today() - __import__("datetime").timedelta(days=2), today=date.today())


def test_penalty_stub_zero() -> None:
    est = estimate_penalty(obligation={"id": "x", "status": "overdue"})
    assert est["penalty_amount"] == 0.0
    assert est["formula"] == "stub"


def test_generation_periods_default() -> None:
    periods = generation_periods(months_ahead=2, today=date(2025, 4, 15))
    assert len(periods) == 2
    assert periods[0] == "2025-04"


def test_apply_status_refresh() -> None:
    ob = {"due_date": (date.today() - __import__("datetime").timedelta(days=1)).isoformat(), "status": "upcoming"}
    out = apply_status_refresh(ob, today=date.today())
    assert out["status"] == "overdue"


def test_legacy_type_map_gstr1() -> None:
    assert LEGACY_TYPE_MAP["GSTR-1"] == "GST_GSTR1"


def test_legacy_type_map_tds() -> None:
    assert LEGACY_TYPE_MAP["TDS"] == "TDS_CHALLAN"


def test_seed_obligations_with_rules_no_hardcode() -> None:
    rules = [{"compliance_code": "GST_GSTR1", "due_day": 11, "month_offset": 1, "frequency": "monthly"}]
    items = seed_obligations_for_period(year=2025, month=4, rules=rules)
    assert len(items) == 1
    assert items[0]["due_date"] == "2025-05-11"


def test_seed_obligations_empty_without_rules() -> None:
    assert seed_obligations_for_period(year=2025, month=4) == []


def test_upcoming_deadlines_filters_completed() -> None:
    today = date.today()
    obs = [
        {"due_date": (today + __import__("datetime").timedelta(days=2)).isoformat(), "status": "upcoming"},
        {"due_date": (today + __import__("datetime").timedelta(days=2)).isoformat(), "status": "completed"},
    ]
    assert len(upcoming_deadlines(obs, within_days=7)) == 1


def test_risk_score_zero_clean() -> None:
    assert compute_risk_score(overdue=[], escalations=[], exposure=0) == 0


def test_risk_score_with_overdue() -> None:
    score = compute_risk_score(overdue=[{"id": "1"}, {"id": "2"}], escalations=[], exposure=0)
    assert score == 20


def test_detect_risks_flags() -> None:
    result = detect_risks(
        obligations=[{"status": "overdue", "compliance_code": "GST_GSTR1"}],
        escalations=[{"id": "e1"}],
        exposure=5000,
    )
    assert result["risk_score"] > 0
    assert len(result["flags"]) >= 2


def test_notice_predictor_elevated() -> None:
    result = predict_notice_risk(risk_flags=[{"severity": "high"}, {"severity": "high"}])
    assert result["notice_risk"] == "elevated"


def test_filing_readiness_full_score() -> None:
    result = filing_readiness_score(
        gst_returns=[{"status": "filed"}],
        reconciliations=[{"match_status": "matched"}],
        tds_liability={"total_liability": 0},
        obligations=[],
    )
    assert result["score"] == 100


def test_filing_readiness_partial() -> None:
    result = filing_readiness_score(gst_returns=[], tds_liability={"total_liability": 50000}, obligations=[])
    assert result["score"] < 100


def test_copilot_overdue_question() -> None:
    answer = answer_compliance_question(
        question="Show overdue obligations",
        dashboard={"overdue": [{"title": "GSTR-1", "due_date": "2025-05-11"}]},
    )
    assert "GSTR-1" in answer["answer"]


def test_copilot_upcoming_question() -> None:
    answer = answer_compliance_question(
        question="What is due this week?",
        dashboard={"upcoming_7d": [{"title": "TDS Challan", "due_date": "2025-07-07", "compliance_code": "TDS_CHALLAN"}]},
    )
    assert "TDS Challan" in answer["answer"]


def test_copilot_default_suggestions() -> None:
    answer = answer_compliance_question(question="hello")
    assert "suggestions" in answer


def test_scheduler_service_has_run_daily() -> None:
    from app.modules.erp.compliance.services.compliance_scheduler_service import ComplianceSchedulerService

    assert callable(getattr(ComplianceSchedulerService, "run_daily", None))
