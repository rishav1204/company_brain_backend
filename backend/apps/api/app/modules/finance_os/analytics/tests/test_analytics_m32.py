from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.finance_os.analytics.engine import kpi_engine, trend_engine
from app.modules.finance_os.analytics.engine.anomaly_engine import detect
from app.modules.finance_os.analytics.engine.benchmark_engine import compare
from app.modules.finance_os.analytics.engine.insight_engine import generate_insights
from app.modules.finance_os.analytics.engine.trend_engine import compute_mom, compute_trend_percent, trend_direction
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read, require_analytics_refresh
from app.modules.platform.events.bus.event_registry import ALL_EVENTS, get_event_definition


# --- trend engine ---


def test_trend_direction_up() -> None:
    assert trend_direction(5.0) == "up"


def test_trend_direction_down() -> None:
    assert trend_direction(-5.0) == "down"


def test_trend_direction_flat() -> None:
    assert trend_direction(0.5) == "flat"


def test_compute_trend_percent_positive() -> None:
    assert compute_trend_percent(110, 100) == 10.0


def test_compute_trend_percent_negative() -> None:
    assert compute_trend_percent(90, 100) == -10.0


def test_compute_trend_percent_zero_prior() -> None:
    assert compute_trend_percent(100, 0) == 100.0


def test_compute_mom_returns_trend() -> None:
    history = [
        {"kpi_code": "collections.dso", "kpi_value": 45},
        {"kpi_code": "collections.dso", "kpi_value": 40},
    ]
    rows = compute_mom(history)
    assert rows[0]["period_key"] == "mom"
    assert rows[0]["trend_direction"] == "up"


def test_compute_mom_insufficient_history() -> None:
    assert compute_mom([{"kpi_value": 1}]) == []


# --- anomaly engine ---


def test_anomaly_cash_runway_low() -> None:
    kpis = [{"kpi_code": "treasury.cash_runway_days", "kpi_value": 15}]
    flags = detect(kpis)
    assert any(f["anomaly_type"] == "cash_burn" for f in flags)


def test_anomaly_compliance_overdue() -> None:
    kpis = [{"kpi_code": "compliance.filing_pct", "kpi_value": 80, "metadata": {"overdue": 2}}]
    flags = detect(kpis)
    assert any(f["anomaly_type"] == "compliance_risk" for f in flags)


def test_anomaly_collection_slowdown() -> None:
    kpis = [{"kpi_code": "collections.dso", "kpi_value": 55}]
    prior = [{"kpi_code": "collections.dso", "kpi_value": 40}]
    flags = detect(kpis, prior_kpis=prior)
    assert any(f["anomaly_type"] == "collection_slowdown" for f in flags)


def test_anomaly_revenue_drop() -> None:
    kpis = [{"kpi_code": "finance.net_profit_margin", "kpi_value": 5}]
    prior = [{"kpi_code": "finance.net_profit_margin", "kpi_value": 25}]
    flags = detect(kpis, prior_kpis=prior)
    assert any(f["anomaly_type"] == "revenue_drop" for f in flags)


# --- insight engine ---


def test_insight_dso_change() -> None:
    kpis = [{"kpi_code": "collections.dso", "kpi_value": 50}]
    prior = [{"kpi_code": "collections.dso", "kpi_value": 40}]
    ins = generate_insights(kpis, prior_kpis=prior)
    assert any(i["insight_type"] == "collections" for i in ins)


def test_insight_cash_runway() -> None:
    kpis = [{"kpi_code": "treasury.cash_runway_days", "kpi_value": 30}]
    ins = generate_insights(kpis)
    assert any(i["insight_type"] == "treasury" for i in ins)


def test_insight_close_efficiency() -> None:
    kpis = [{"kpi_code": "close.efficiency_score", "kpi_value": 45}]
    ins = generate_insights(kpis)
    assert any(i["insight_type"] == "close" for i in ins)


def test_insight_forecast_accuracy() -> None:
    kpis = [{"kpi_code": "forecast.accuracy_avg", "kpi_value": 25}]
    ins = generate_insights(kpis)
    assert any(i["insight_type"] == "forecast" for i in ins)


def test_insight_profitability_change() -> None:
    kpis = [{"kpi_code": "finance.net_profit_margin", "kpi_value": 8}]
    prior = [{"kpi_code": "finance.net_profit_margin", "kpi_value": 12}]
    ins = generate_insights(kpis, prior_kpis=prior)
    assert any(i["insight_type"] == "profitability" for i in ins)


def test_anomaly_no_flags_when_healthy() -> None:
    kpis = [
        {"kpi_code": "treasury.cash_runway_days", "kpi_value": 90},
        {"kpi_code": "compliance.filing_pct", "kpi_value": 100, "metadata": {"overdue": 0}},
    ]
    assert detect(kpis) == []


def test_kpi_engine_not_ready_finance() -> None:
    with patch("app.modules.finance_os.analytics.engine.kpi_engine.finance_read_models") as mock_fin:
        mock_fin.load_finance.return_value = {"ready": False}
        with patch("app.modules.finance_os.analytics.engine.kpi_engine.treasury_read_models") as mock_tre:
            mock_tre.load_treasury.return_value = {"available_cash": 0, "liquidity_coverage": None}
            with patch("app.modules.finance_os.analytics.engine.kpi_engine.compliance_read_models") as mock_c:
                mock_c.load_compliance.return_value = {"filing_compliance_pct": 0, "penalty_exposure": 0, "overdue_count": 0}
                with patch("app.modules.finance_os.analytics.engine.kpi_engine.reconciliation_read_models") as mock_r:
                    mock_r.load_reconciliation.return_value = {"reconciliation_rate": 0}
                    with patch("app.modules.finance_os.analytics.engine.kpi_engine.workflow_read_models") as mock_w:
                        mock_w.load_close.return_value = {"efficiency_score": 0, "sla_breach_count": 0}
                        with patch("app.modules.finance_os.analytics.engine.kpi_engine.forecast_read_models") as mock_f:
                            mock_f.load_forecast_accuracy.return_value = {"accuracy_avg": None}
                            mock_f.load_forecast.return_value = {"avg_daily_forecast": 1}
                            kpis = kpi_engine.compute_all("org")
                            codes = {k["kpi_code"] for k in kpis}
                            assert "finance.gross_profit_margin" not in codes
                            assert "treasury.cash_runway_days" in codes


# --- guards ---


def test_guard_read_cfo() -> None:
    require_analytics_read(MagicMock(roles=["cfo"]))


def test_guard_read_board() -> None:
    require_analytics_read(MagicMock(roles=["board_viewer"]))


def test_guard_read_denied() -> None:
    with pytest.raises(HTTPException) as exc:
        require_analytics_read(MagicMock(roles=["guest"]))
    assert exc.value.status_code == 403


def test_guard_refresh_controller() -> None:
    require_analytics_refresh(MagicMock(roles=["controller"]))


def test_guard_refresh_denied() -> None:
    with pytest.raises(HTTPException):
        require_analytics_refresh(MagicMock(roles=["accountant"]))


# --- event registry ---


def test_event_kpi_updated() -> None:
    assert "kpi.updated" in ALL_EVENTS
    assert get_event_definition("kpi.updated").owner == "finance_os.analytics"


def test_event_insight_generated() -> None:
    assert "insight.generated" in ALL_EVENTS


def test_event_risk_detected() -> None:
    assert "risk.detected" in ALL_EVENTS


def test_event_dashboard_refreshed() -> None:
    assert "dashboard.refreshed" in ALL_EVENTS


def test_event_analytics_refresh_requested() -> None:
    assert "analytics.refresh.requested" in ALL_EVENTS


def test_event_scheduler_analytics_daily() -> None:
    assert "scheduler.analytics.daily" in ALL_EVENTS


# --- job registry ---


def test_job_registry_analytics_daily() -> None:
    from app.modules.platform.events.scheduler.job_registry import SCHEDULED_JOBS

    assert SCHEDULED_JOBS.get("analytics_daily") == "scheduler.analytics.daily"


# --- kpi engine mocked ---


@patch("app.modules.finance_os.analytics.engine.kpi_engine.forecast_read_models")
@patch("app.modules.finance_os.analytics.engine.kpi_engine.workflow_read_models")
@patch("app.modules.finance_os.analytics.engine.kpi_engine.reconciliation_read_models")
@patch("app.modules.finance_os.analytics.engine.kpi_engine.compliance_read_models")
@patch("app.modules.finance_os.analytics.engine.kpi_engine.treasury_read_models")
@patch("app.modules.finance_os.analytics.engine.kpi_engine.finance_read_models")
def test_kpi_engine_compute_all(mock_fin, mock_tre, mock_comp, mock_rec, mock_wf, mock_fc) -> None:
    mock_fin.load_finance.return_value = {
        "ready": True,
        "fiscal_period_id": "fp1",
        "revenue": 1000,
        "expense": 400,
        "gross_profit": 600,
        "net_profit": 500,
        "ar_outstanding": 200,
        "ap_outstanding": 100,
    }
    mock_fin.days_in_period.return_value = 30
    mock_tre.load_treasury.return_value = {"available_cash": 5000, "liquidity_coverage": 1.5}
    mock_comp.load_compliance.return_value = {"filing_compliance_pct": 95, "penalty_exposure": 0, "overdue_count": 0}
    mock_rec.load_reconciliation.return_value = {"reconciliation_rate": 98}
    mock_wf.load_close.return_value = {"close_duration_days": 3, "efficiency_score": 80, "sla_breach_count": 0}
    mock_fc.load_forecast_accuracy.return_value = {"accuracy_avg": 5.0, "rows": [{}]}
    mock_fc.load_forecast.return_value = {"avg_daily_forecast": 100}
    kpis = kpi_engine.compute_all("org")
    codes = {k["kpi_code"] for k in kpis}
    assert "finance.gross_profit_margin" in codes
    assert "collections.dso" in codes
    assert "treasury.cash_runway_days" in codes


# --- analytics engine refresh mocked ---


@patch("app.modules.finance_os.analytics.engine.analytics_engine.insight_repository")
@patch("app.modules.finance_os.analytics.engine.analytics_engine.anomaly_flag_repository")
@patch("app.modules.finance_os.analytics.engine.analytics_engine.kpi_trend_repository")
@patch("app.modules.finance_os.analytics.engine.analytics_engine.kpi_snapshot_repository")
@patch("app.modules.finance_os.analytics.engine.analytics_engine.kpi_engine")
def test_refresh_kpis(mock_ke, mock_snap, mock_trend, mock_anom, mock_ins) -> None:
    from app.modules.finance_os.analytics.engine.analytics_engine import refresh_kpis

    mock_snap.list.return_value = []
    mock_ke.compute_all.return_value = [
        {"kpi_code": "collections.dso", "kpi_value": 40, "snapshot_date": "2026-06-01", "metadata": {}},
        {"kpi_code": "treasury.cash_runway_days", "kpi_value": 60, "snapshot_date": "2026-06-01", "metadata": {}},
    ]
    mock_snap.upsert.return_value = {}
    mock_snap.history.return_value = [
        {"kpi_code": "collections.dso", "kpi_value": 40},
        {"kpi_code": "collections.dso", "kpi_value": 35},
    ]
    mock_anom.clear_for_org.return_value = 0
    mock_ins.create.return_value = {}
    result = refresh_kpis("org")
    assert result["kpis"] == 2


# --- benchmark ---


@patch("app.modules.finance_os.analytics.engine.benchmark_engine.kpi_snapshot_repository")
def test_benchmark_compare(mock_repo) -> None:
    mock_repo.history.return_value = [
        {"kpi_value": 100, "snapshot_date": "2026-06-01"},
        {"kpi_value": 90, "snapshot_date": "2026-05-01"},
    ]
    result = compare("org", kpi_code="collections.dso")
    assert result["kpi_code"] == "collections.dso"
    assert len(result["benchmarks"]) >= 2


# --- services read finance_analytics only ---


@patch("app.modules.finance_os.analytics.services.kpi_service.kpi_snapshot_repository")
@patch("app.modules.finance_os.analytics.services.kpi_service.analytics_schema_repository")
def test_kpi_service_list(mock_schema, mock_repo) -> None:
    from app.modules.finance_os.analytics.services.kpi_service import kpi_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list.return_value = [{"kpi_code": "collections.dso", "kpi_value": 40}]
    items = kpi_service.list("org")
    assert items[0]["kpi_code"] == "collections.dso"


@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.dashboard_snapshot_repository")
@patch("app.modules.finance_os.analytics.services.executive_dashboard_service.analytics_schema_repository")
def test_dashboard_from_cache(mock_schema, mock_dash) -> None:
    from app.modules.finance_os.analytics.services.executive_dashboard_service import executive_dashboard_service

    mock_schema.schema_ready.return_value = True
    mock_dash.get_latest.return_value = {
        "snapshot_date": "2026-06-01",
        "refreshed_at": "2026-06-01T00:00:00",
        "payload": {"widgets": {"cash_position": {"kpi_value": 60}}},
    }
    data = executive_dashboard_service.get("org")
    assert data["widgets"]["cash_position"]["kpi_value"] == 60


# --- AI ---


@patch("app.modules.finance_os.analytics.ai.executive_copilot.llm_provider")
@patch("app.modules.finance_os.analytics.ai.executive_copilot.legacy_build_context")
def test_executive_copilot_fallback(mock_ctx, mock_llm) -> None:
    from app.modules.finance_os.analytics.ai.executive_copilot import answer

    mock_ctx.return_value = "KPI context"
    mock_llm.is_ready.return_value = False
    result = answer("org", "Why did margin drop?")
    assert "answer" in result
    assert result["confidence_band"] == "review"


@patch("app.modules.finance_os.analytics.ai.insight_generator.llm_provider")
@patch("app.modules.finance_os.analytics.ai.insight_generator.kpi_snapshot_repository")
@patch("app.modules.finance_os.analytics.ai.insight_generator.insight_engine")
def test_insight_generator_no_llm(mock_ie, mock_repo, mock_llm) -> None:
    from app.modules.finance_os.analytics.ai.insight_generator import generate

    mock_repo.list.return_value = [{"kpi_code": "collections.dso", "kpi_value": 40}]
    mock_ie.generate_insights.return_value = [{"insight_type": "collections", "title": "T", "description": "D", "severity": "info", "evidence": {}}]
    mock_llm.is_ready.return_value = False
    rows = generate("org")
    assert len(rows) == 1


def test_risk_analyzer_synthesize_empty() -> None:
    from app.modules.finance_os.analytics.ai.risk_analyzer import synthesize

    with patch("app.modules.finance_os.analytics.ai.risk_analyzer.anomaly_flag_repository") as mock_repo:
        mock_repo.list_recent.return_value = []
        result = synthesize("org")
        assert result["risk_level"] == "low"


def test_recommendation_engine_suggest() -> None:
    from app.modules.finance_os.analytics.ai.recommendation_engine import suggest

    with patch("app.modules.finance_os.analytics.ai.recommendation_engine.insight_repository") as mock_repo:
        mock_repo.list.return_value = [{"id": "1", "insight_type": "treasury", "title": "Runway", "severity": "high"}]
        actions = suggest("org")
        assert actions[0]["recommended_action"]


def test_trend_reasoner_explain_no_llm() -> None:
    from app.modules.finance_os.analytics.ai.trend_reasoner import explain

    with patch("app.modules.finance_os.analytics.ai.trend_reasoner.llm_provider") as mock_llm:
        mock_llm.is_ready.return_value = False
        text = explain(kpi_code="collections.dso", trend_direction="up", trend_percent=10.0)
        assert "collections.dso" in text


# --- consumer wiring ---


def test_consume_analytics_refresh_import() -> None:
    from app.services.event_consumers import _consume_analytics_refresh

    assert callable(_consume_analytics_refresh)


@patch("app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline.run_refresh")
@patch("app.modules.finance_os.analytics.repositories.schema_repository.analytics_schema_repository")
def test_consume_analytics_refresh_triggers(mock_schema, mock_run) -> None:
    from app.services.event_consumers import _consume_analytics_refresh

    mock_schema.schema_ready.return_value = True
    _consume_analytics_refresh({"event_type": "report.generated", "org_id": "org1", "trace_id": "t1", "payload": {}})
    mock_run.assert_called_once()


@patch("app.modules.finance_os.analytics.repositories.schema_repository.analytics_schema_repository")
def test_consume_analytics_skips_unknown(mock_schema) -> None:
    from app.services.event_consumers import _consume_analytics_refresh

    _consume_analytics_refresh({"event_type": "unknown", "org_id": "org1"})
    mock_schema.schema_ready.assert_not_called()


# --- forecast accuracy query ---


def test_variance_percent_symmetric() -> None:
    from app.modules.finance_os.forecasting.services.forecast_accuracy_service import variance_percent

    assert variance_percent(actual=110, forecast=100) == 10.0
    assert variance_percent(actual=90, forecast=-100) == 190.0


@patch("app.modules.finance_os.forecasting.services.forecast_accuracy_query_service.get_db_conn")
def test_list_org_accuracy(mock_db) -> None:
    from app.modules.finance_os.forecasting.services.forecast_accuracy_query_service import list_org_accuracy

    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [{"variance_percent": 5.0}]
    conn.cursor.return_value.__enter__.return_value = cur
    mock_db.return_value.__enter__.return_value = conn
    rows = list_org_accuracy("org")
    assert rows[0]["variance_percent"] == 5.0


# --- forecast accuracy job proxy ---


@patch("app.modules.finance_os.forecasting.jobs.forecast_accuracy_job.record_accuracy")
@patch("app.modules.finance_os.forecasting.jobs.forecast_accuracy_job.forecast_repository")
@patch("app.modules.finance_os.forecasting.jobs.forecast_accuracy_job._actual_proxy")
def test_accuracy_job_uses_proxy(mock_proxy, mock_repo, mock_rec) -> None:
    from app.modules.finance_os.forecasting.jobs.forecast_accuracy_job import run_accuracy

    mock_repo.schema_ready.return_value = True
    mock_repo.list_latest.return_value = [{"id": "f1", "forecast_value": 100}]
    mock_proxy.return_value = 120
    mock_rec.return_value = {"id": "a1"}
    result = run_accuracy("org", forecast_type="cash")
    assert result["count"] == 1


# --- forecast report variance ---


def test_forecast_report_variance() -> None:
    from unittest.mock import MagicMock
    from app.modules.erp.reporting.services.forecast_report_service import forecast_report_service

    mock_forecast = MagicMock()
    mock_forecast.get_series.return_value = {"items": [{"forecast_value": 100, "forecast_date": "2026-06-01"}]}
    mock_forecast.actual_proxy.return_value = 110
    with patch(
        "app.modules.erp.reporting.services.forecast_report_service.intelligence_registry.forecast",
        return_value=mock_forecast,
    ):
        data = forecast_report_service.get("org", forecast_type="cash")
    assert data["variance"][0]["variance_percent"] == 10.0


# --- router ---


def test_analytics_router_prefix() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("routes", "router.py").read_text(encoding="utf-8")
    assert 'prefix="/finance-os/analytics"' in text


def test_main_wires_analytics() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[4].joinpath("main.py").read_text(encoding="utf-8")
    assert "finance_os_analytics_router" in text


# --- langgraph ---


def test_langgraph_executive_copilot_key() -> None:
    from app.services.langgraph_runner import _normalize_agent_key

    assert _normalize_agent_key("executive_copilot") == "executive_copilot"


# --- scheduling ---


@patch("app.modules.platform.events.services.scheduling_service.platform_event_service")
def test_scheduling_emit_analytics_daily(mock_pub) -> None:
    from app.modules.platform.events.services.scheduling_service import scheduling_service

    scheduling_service.emit_analytics_daily("org1")
    assert mock_pub.publish.call_args.kwargs["event_type"] == "scheduler.analytics.daily"


# --- events emit ---


@patch("app.modules.finance_os.analytics.events.analytics_events.platform_event_service")
def test_emit_kpi_updated(mock_pub) -> None:
    from app.modules.finance_os.analytics.events.analytics_events import emit_kpi_updated

    emit_kpi_updated("org1", count=5)
    assert mock_pub.publish.call_args.kwargs["event_type"] == "kpi.updated"


# --- close analytics ---


@patch("app.modules.finance_os.analytics.services.close_analytics_service.workflow_read_models")
@patch("app.modules.finance_os.analytics.services.close_analytics_service.kpi_snapshot_repository")
@patch("app.modules.finance_os.analytics.services.close_analytics_service.analytics_schema_repository")
def test_close_analytics_service(mock_schema, mock_kpi, mock_wf) -> None:
    from app.modules.finance_os.analytics.services.close_analytics_service import close_analytics_service

    mock_schema.schema_ready.return_value = True
    mock_wf.load_close.return_value = {"efficiency_score": 75}
    mock_kpi.list.return_value = []
    item = close_analytics_service.get("org")
    assert item["close"]["efficiency_score"] == 75


# --- anomaly service ---


@patch("app.modules.finance_os.analytics.services.anomaly_analytics_service.anomaly_flag_repository")
@patch("app.modules.finance_os.analytics.services.anomaly_analytics_service.analytics_schema_repository")
def test_anomaly_service(mock_schema, mock_repo) -> None:
    from app.modules.finance_os.analytics.services.anomaly_analytics_service import anomaly_analytics_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list_recent.return_value = [{"anomaly_type": "cash_burn"}]
    items = anomaly_analytics_service.list("org")
    assert items[0]["anomaly_type"] == "cash_burn"


# --- trend service ---


@patch("app.modules.finance_os.analytics.services.trend_service.kpi_trend_repository")
@patch("app.modules.finance_os.analytics.services.trend_service.analytics_schema_repository")
def test_trend_service(mock_schema, mock_repo) -> None:
    from app.modules.finance_os.analytics.services.trend_service import trend_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list.return_value = [{"kpi_code": "collections.dso", "trend_percent": 5}]
    items = trend_service.list("org", kpi_code="collections.dso")
    assert items[0]["trend_percent"] == 5


# --- benchmark service ---


@patch("app.modules.finance_os.analytics.services.benchmark_service.benchmark_engine")
@patch("app.modules.finance_os.analytics.services.benchmark_service.kpi_snapshot_repository")
@patch("app.modules.finance_os.analytics.services.benchmark_service.analytics_schema_repository")
def test_benchmark_service_list_all(mock_schema, mock_snap, mock_be) -> None:
    from app.modules.finance_os.analytics.services.benchmark_service import benchmark_service

    mock_schema.schema_ready.return_value = True
    mock_snap.list.return_value = [
        {"kpi_code": "collections.dso"},
        {"kpi_code": "treasury.cash_runway_days"},
    ]
    mock_be.compare.side_effect = lambda org, kpi_code: {"kpi_code": kpi_code, "benchmarks": []}
    items = benchmark_service.list("org")
    assert len(items) == 2
    assert items[0]["kpi_code"] == "collections.dso"


@patch("app.modules.finance_os.analytics.services.benchmark_service.benchmark_engine")
@patch("app.modules.finance_os.analytics.services.benchmark_service.analytics_schema_repository")
def test_benchmark_service(mock_schema, mock_be) -> None:
    from app.modules.finance_os.analytics.services.benchmark_service import benchmark_service

    mock_schema.schema_ready.return_value = True
    mock_be.compare.return_value = {"kpi_code": "x", "benchmarks": []}
    item = benchmark_service.compare("org", kpi_code="collections.dso")
    assert item["kpi_code"] == "x"


# --- insight service ---


@patch("app.modules.finance_os.analytics.services.insight_service.insight_repository")
@patch("app.modules.finance_os.analytics.services.insight_service.analytics_schema_repository")
def test_insight_service(mock_schema, mock_repo) -> None:
    from app.modules.finance_os.analytics.services.insight_service import insight_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list.return_value = [{"title": "DSO up"}]
    items = insight_service.list("org")
    assert items[0]["title"] == "DSO up"


# --- executive reasoner ---


@patch("app.modules.finance_os.analytics.ai.executive_reasoner.executive_dashboard_service")
def test_executive_reasoner_build_context(mock_dash) -> None:
    from app.modules.finance_os.analytics.ai.executive_reasoner import build_context

    mock_dash.get.return_value = {"snapshot_date": "2026-06-01", "widgets": {}}
    ctx = build_context("org", "margin?")
    assert "margin?" in ctx


# --- aggregation variance aligned ---


def test_compute_forecast_variance_uses_m30() -> None:
    from app.modules.erp.reporting.engine.aggregation_engine import compute_forecast_variance

    assert compute_forecast_variance(actual=110, forecast=100) == 10.0
