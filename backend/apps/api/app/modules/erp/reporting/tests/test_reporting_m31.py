from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.erp.accounts_payable.engine.aging_engine import aging_bucket, aging_days, bucket_invoice
from app.modules.erp.reporting.engine.aggregation_engine import (
    BUCKET_MAP,
    aggregate_statement,
    compute_forecast_variance,
)
from app.modules.erp.reporting.engine.export_engine import export_csv, export_pdf, render_export
from app.modules.erp.reporting.engine.reporting_cache_engine import get_cached, is_stale, set_cached
from app.modules.erp.reporting.security.reporting_guard import require_reporting_export, require_reporting_read
from app.modules.erp.reporting.services.report_engine import report_engine
from app.modules.platform.events.bus.event_registry import ALL_EVENTS, get_event_definition


# --- aging engine ---


def test_aging_days_not_overdue() -> None:
    assert aging_days(due_date="2026-06-20", as_of="2026-06-20") == 0


def test_aging_days_overdue() -> None:
    assert aging_days(due_date="2026-06-01", as_of="2026-06-20") == 19


def test_aging_bucket_current() -> None:
    assert aging_bucket(0) == "current"


def test_aging_bucket_1_30() -> None:
    assert aging_bucket(15) == "1-30"


def test_aging_bucket_31_60() -> None:
    assert aging_bucket(45) == "31-60"


def test_aging_bucket_61_90() -> None:
    assert aging_bucket(75) == "61-90"


def test_aging_bucket_90_plus() -> None:
    assert aging_bucket(120) == "90+"


def test_bucket_invoice_outstanding_calc() -> None:
    inv = {"due_date": "2026-01-01", "total_amount": 1000, "paid_amount": 200}
    item = bucket_invoice(inv, as_of="2026-02-01")
    assert item["outstanding"] == 800
    assert item["bucket"] == "31-60"


def test_bucket_map_has_all_buckets() -> None:
    assert set(BUCKET_MAP.keys()) == {"current", "1-30", "31-60", "61-90", "90+"}


# --- variance ---


def test_compute_forecast_variance_positive() -> None:
    assert compute_forecast_variance(actual=110, forecast=100) == 10.0


def test_compute_forecast_variance_negative() -> None:
    assert compute_forecast_variance(actual=90, forecast=100) == -10.0


def test_compute_forecast_variance_zero_forecast() -> None:
    assert compute_forecast_variance(actual=100, forecast=0) is None


# --- cache ---


def test_cache_set_and_get() -> None:
    set_cached("org1", "trial_balance", {"p": "1"}, {"ok": True}, ttl=60.0)
    assert get_cached("org1", "trial_balance", {"p": "1"}) == {"ok": True}


def test_cache_miss_different_params() -> None:
    assert get_cached("org1", "trial_balance", {"p": "2"}) is None


def test_is_stale_none() -> None:
    assert is_stale(None) is True


def test_is_stale_recent() -> None:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).isoformat()
    assert is_stale(ts, max_age_seconds=3600) is False


# --- export ---


def test_export_csv_trial_balance() -> None:
    payload = {"lines": [{"account_code": "1000", "account_name": "Cash", "debit_total": 100, "credit_total": 0, "balance": 100}]}
    data = export_csv("trial_balance", payload)
    text = data.decode("utf-8")
    assert "1000" in text
    assert "Cash" in text


def test_export_csv_ap_aging() -> None:
    payload = {"lines": [{"entity_id": "v1", "entity_name": "Vendor", "bucket_current": 10, "bucket_1_30": 0, "bucket_31_60": 0, "bucket_61_90": 0, "bucket_90_plus": 0, "total_outstanding": 10}]}
    data = export_csv("ap_aging", payload)
    assert b"Vendor" in data


def test_export_pdf_trial_balance() -> None:
    payload = {"lines": [{"account_code": "1000", "account_name": "Cash", "debit_total": 100, "credit_total": 0, "balance": 100}]}
    pdf = export_pdf("trial_balance", payload)
    assert pdf[:4] == b"%PDF"


def test_render_export_csv_default() -> None:
    content, mime = render_export("pnl", {"sections": []}, fmt="csv")
    assert mime == "text/csv"
    assert b"pnl" in content


def test_render_export_pdf() -> None:
    content, mime = render_export("pnl", {"sections": [{"reporting_category": "Revenue", "amount": 100}]}, fmt="pdf")
    assert mime == "application/pdf"
    assert content[:4] == b"%PDF"


# --- report engine ---


def test_report_engine_should_async_large() -> None:
    assert report_engine.should_async("trial_balance", row_count=6000) is True


def test_report_engine_should_sync_small() -> None:
    assert report_engine.should_async("trial_balance", row_count=100) is False


def test_report_engine_should_async_gst() -> None:
    assert report_engine.should_async("gst", row_count=200) is True


def test_report_engine_unsupported_type() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        report_engine.fetch_payload("org", report_type="unknown", filters={})


@patch("app.modules.erp.reporting.services.report_engine.trial_balance_service")
def test_report_engine_fetch_trial_balance(mock_tb) -> None:
    mock_tb.get_from_reporting.return_value = {"lines": []}
    report_engine.fetch_payload("org", report_type="trial_balance", filters={"fiscal_period_id": "fp1"})
    mock_tb.get_from_reporting.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.pnl_service")
def test_report_engine_fetch_pnl(mock_pnl) -> None:
    mock_pnl.get.return_value = {"sections": []}
    report_engine.fetch_payload("org", report_type="pnl", filters={"fiscal_period_id": "fp1"})
    mock_pnl.get.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.balance_sheet_service")
def test_report_engine_fetch_balance_sheet(mock_bs) -> None:
    mock_bs.get.return_value = {"sections": []}
    report_engine.fetch_payload("org", report_type="balance_sheet", filters={"fiscal_period_id": "fp1"})
    mock_bs.get.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.aging_report_service")
def test_report_engine_fetch_ap_aging(mock_aging) -> None:
    mock_aging.get_ap.return_value = {"lines": []}
    report_engine.fetch_payload("org", report_type="ap_aging", filters={})
    mock_aging.get_ap.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.aging_report_service")
def test_report_engine_fetch_ar_aging(mock_aging) -> None:
    mock_aging.get_ar.return_value = {"lines": []}
    report_engine.fetch_payload("org", report_type="ar_aging", filters={})
    mock_aging.get_ar.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.gst_report_service")
def test_report_engine_fetch_gst(mock_gst) -> None:
    mock_gst.get.return_value = {"payload": {}}
    report_engine.fetch_payload("org", report_type="gst", filters={"return_period": "2026-01"})
    mock_gst.get.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.tds_report_service")
def test_report_engine_fetch_tds(mock_tds) -> None:
    mock_tds.get.return_value = {"payload": {}}
    report_engine.fetch_payload("org", report_type="tds", filters={"return_period": "2026-Q1"})
    mock_tds.get.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.treasury_report_service")
def test_report_engine_fetch_treasury(mock_tr) -> None:
    mock_tr.cash_position.return_value = {}
    report_engine.fetch_payload("org", report_type="treasury_cash", filters={})
    mock_tr.cash_position.assert_called_once()


@patch("app.modules.erp.reporting.services.report_engine.forecast_report_service")
def test_report_engine_fetch_forecast(mock_fc) -> None:
    mock_fc.get.return_value = {"items": []}
    report_engine.fetch_payload("org", report_type="forecast", filters={"forecast_type": "cash"})
    mock_fc.get.assert_called_once()


# --- guards ---


def test_guard_read_allowed_accountant() -> None:
    user = MagicMock(roles=["accountant"])
    require_reporting_read(user)


def test_guard_read_allowed_auditor() -> None:
    user = MagicMock(roles=["auditor"])
    require_reporting_read(user)


def test_guard_read_denied() -> None:
    user = MagicMock(roles=["guest"])
    with pytest.raises(HTTPException) as exc:
        require_reporting_read(user)
    assert exc.value.status_code == 403


def test_guard_export_allowed_cfo() -> None:
    user = MagicMock(roles=["cfo"])
    require_reporting_export(user)


def test_guard_export_denied_accountant() -> None:
    user = MagicMock(roles=["accountant"])
    with pytest.raises(HTTPException):
        require_reporting_export(user)


# --- event registry ---


def test_event_registry_report_generated() -> None:
    assert "report.generated" in ALL_EVENTS
    assert get_event_definition("report.generated").owner == "erp.reporting"


def test_event_registry_report_exported() -> None:
    assert "report.exported" in ALL_EVENTS


def test_event_registry_report_snapshot_created() -> None:
    assert "report.snapshot.created" in ALL_EVENTS


def test_event_registry_reports_generate_requested() -> None:
    assert "reports.generate.requested" in ALL_EVENTS


def test_event_registry_reports_generate_completed() -> None:
    assert "reports.generate.completed" in ALL_EVENTS


def test_event_registry_reports_refresh_requested() -> None:
    assert "reports.refresh.requested" in ALL_EVENTS


def test_event_registry_scheduler_reports_daily() -> None:
    assert "scheduler.reports.daily" in ALL_EVENTS


# --- job registry ---


def test_job_registry_reports_daily() -> None:
    from app.modules.platform.events.scheduler.job_registry import SCHEDULED_JOBS

    assert SCHEDULED_JOBS.get("reports_daily") == "scheduler.reports.daily"


# --- cash flow stub ---


def test_cash_flow_phase2_stub() -> None:
    from app.modules.erp.reporting.services.cash_flow_service import cash_flow_service

    item = cash_flow_service.get("org", fiscal_period_id="fp1")
    assert item["status"] == "phase2"
    assert item["sections"] == []


# --- aggregation statement rollup (mocked) ---


@patch("app.modules.erp.reporting.engine.aggregation_engine.balance_repository")
@patch("app.modules.erp.reporting.engine.aggregation_engine.mapping_repository")
def test_aggregate_statement_pnl(mock_map, mock_bal) -> None:
    mock_map.list_financial_mappings.return_value = [
        {"account_id": "a1", "statement_type": "profit_loss", "reporting_category": "Revenue"},
        {"account_id": "a2", "statement_type": "profit_loss", "reporting_category": "Expenses"},
    ]
    mock_bal.list_by_period.return_value = [
        {"account_id": "a1", "closing_balance": 1000},
        {"account_id": "a2", "closing_balance": 400},
    ]
    rows = aggregate_statement("org", fiscal_period_id="fp1", statement_type="profit_loss")
    by_cat = {r["reporting_category"]: r["amount"] for r in rows}
    assert by_cat["Revenue"] == 1000
    assert by_cat["Expenses"] == 400


@patch("app.modules.erp.reporting.engine.aggregation_engine.balance_repository")
@patch("app.modules.erp.reporting.engine.aggregation_engine.mapping_repository")
def test_aggregate_statement_balance_sheet(mock_map, mock_bal) -> None:
    mock_map.list_financial_mappings.return_value = [
        {"account_id": "a1", "statement_type": "balance_sheet", "reporting_category": "Assets"},
    ]
    mock_bal.list_by_period.return_value = [{"account_id": "a1", "closing_balance": 5000}]
    rows = aggregate_statement("org", fiscal_period_id="fp1", statement_type="balance_sheet")
    assert rows[0]["amount"] == 5000


# --- materialization (mocked) ---


@patch("app.modules.erp.reporting.engine.materialization_engine.trial_balance_repository")
@patch("app.modules.erp.reporting.engine.materialization_engine.aggregation_engine")
def test_refresh_trial_balance(mock_agg, mock_repo) -> None:
    from app.modules.erp.reporting.engine.materialization_engine import refresh_trial_balance

    mock_agg.aggregate_trial_balance.return_value = [{"account_id": "a1", "debit_total": 100, "credit_total": 100, "balance": 0}]
    mock_repo.replace_period.return_value = 1
    result = refresh_trial_balance("org", fiscal_period_id="fp1")
    assert result["lines"] == 1


@patch("app.modules.erp.reporting.engine.materialization_engine.pnl_repository")
@patch("app.modules.erp.reporting.engine.materialization_engine.aggregation_engine")
def test_refresh_pnl(mock_agg, mock_repo) -> None:
    from app.modules.erp.reporting.engine.materialization_engine import refresh_pnl

    mock_agg.aggregate_statement.return_value = [{"reporting_category": "Revenue", "amount": 100}]
    mock_repo.replace_period.return_value = 1
    result = refresh_pnl("org", fiscal_period_id="fp1")
    assert result["categories"] == 1


@patch("app.modules.erp.reporting.engine.materialization_engine.balance_sheet_repository")
@patch("app.modules.erp.reporting.engine.materialization_engine.aggregation_engine")
def test_refresh_balance_sheet(mock_agg, mock_repo) -> None:
    from app.modules.erp.reporting.engine.materialization_engine import refresh_balance_sheet

    mock_agg.aggregate_statement.return_value = [{"reporting_category": "Assets", "amount": 100}]
    mock_repo.replace_period.return_value = 1
    result = refresh_balance_sheet("org", fiscal_period_id="fp1")
    assert result["report"] == "balance_sheet"


@patch("app.modules.erp.reporting.engine.materialization_engine.ap_aging_repository")
@patch("app.modules.erp.reporting.engine.materialization_engine.aggregation_engine")
def test_refresh_ap_aging(mock_agg, mock_repo) -> None:
    from app.modules.erp.reporting.engine.materialization_engine import refresh_ap_aging

    mock_agg.aggregate_ap_aging.return_value = []
    mock_repo.replace_as_of.return_value = 0
    result = refresh_ap_aging("org")
    assert result["report"] == "ap_aging"


@patch("app.modules.erp.reporting.engine.materialization_engine.ar_aging_repository")
@patch("app.modules.erp.reporting.engine.materialization_engine.aggregation_engine")
def test_refresh_ar_aging(mock_agg, mock_repo) -> None:
    from app.modules.erp.reporting.engine.materialization_engine import refresh_ar_aging

    mock_agg.aggregate_ar_aging.return_value = []
    mock_repo.replace_as_of.return_value = 0
    result = refresh_ar_aging("org")
    assert result["report"] == "ar_aging"


# --- consumer wiring ---


def test_consume_reports_event_import() -> None:
    from app.services.event_consumers import _consume_reports_event

    assert callable(_consume_reports_event)


def test_consume_reporting_refresh_import() -> None:
    from app.services.event_consumers import _consume_reporting_refresh

    assert callable(_consume_reporting_refresh)


@patch("app.modules.erp.reporting.repositories.schema_repository.reporting_schema_repository")
def test_consume_reporting_refresh_skips_unknown_event(mock_schema) -> None:
    from app.services.event_consumers import _consume_reporting_refresh

    mock_schema.schema_ready.return_value = True
    _consume_reporting_refresh({"event_type": "unknown.event", "org_id": "org1"})
    mock_schema.schema_ready.assert_not_called()


@patch("app.modules.erp.reporting.pipelines.report_refresh_pipeline.run_refresh")
@patch("app.modules.erp.reporting.repositories.schema_repository.reporting_schema_repository")
def test_consume_reporting_refresh_triggers(mock_schema, mock_refresh) -> None:
    from app.services.event_consumers import _consume_reporting_refresh

    mock_schema.schema_ready.return_value = True
    _consume_reporting_refresh({"event_type": "journal.posted", "org_id": "org1", "trace_id": "t1", "payload": {}})
    mock_refresh.assert_called_once()


# --- router prefix ---


def test_reporting_router_prefix() -> None:
    from app.modules.erp.reporting.routes.router import router

    assert router.prefix == "/erp/reports"


# --- pnl service meta ---


@patch("app.modules.erp.reporting.services.pnl_service.pnl_repository")
@patch("app.modules.erp.reporting.services.pnl_service.reporting_schema_repository")
@patch("app.modules.erp.reporting.services.pnl_service.materialization_engine")
def test_pnl_service_meta(mock_mat, mock_schema, mock_repo) -> None:
    from app.modules.erp.reporting.services.pnl_service import pnl_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list_period.return_value = [
        {"reporting_category": "Revenue", "amount": 1000, "refreshed_at": "2026-01-01"},
        {"reporting_category": "Operating Expense", "amount": 300, "refreshed_at": "2026-01-01"},
    ]
    item = pnl_service.get("org", fiscal_period_id="fp1", refresh_if_missing=False)
    assert item["meta"]["revenue_total"] == 1000
    assert item["meta"]["gross_profit"] == 700


# --- balance sheet validation ---


@patch("app.modules.erp.reporting.services.balance_sheet_service.balance_sheet_repository")
@patch("app.modules.erp.reporting.services.balance_sheet_service.reporting_schema_repository")
def test_balance_sheet_balanced_flag(mock_schema, mock_repo) -> None:
    from app.modules.erp.reporting.services.balance_sheet_service import balance_sheet_service

    mock_schema.schema_ready.return_value = True
    mock_repo.list_period.return_value = [
        {"reporting_category": "Assets", "amount": 1000, "refreshed_at": "2026-01-01"},
        {"reporting_category": "Liabilities", "amount": 600, "refreshed_at": "2026-01-01"},
        {"reporting_category": "Equity", "amount": 400, "refreshed_at": "2026-01-01"},
    ]
    item = balance_sheet_service.get("org", fiscal_period_id="fp1", refresh_if_missing=False)
    assert item["meta"]["balanced"] is True


# --- trial balance balanced flag ---


@patch("app.modules.erp.reporting.services.trial_balance_service.trial_balance_repository")
@patch("app.modules.erp.reporting.services.trial_balance_service.reporting_schema_repository")
def test_trial_balance_balanced(mock_schema, mock_repo) -> None:
    from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service

    mock_schema.schema_ready.return_value = True
    mock_repo.has_data.return_value = True
    mock_repo.list_period.return_value = ([], None)
    mock_repo.totals.return_value = {"debit_total": 100, "credit_total": 100, "refreshed_at": "2026-01-01"}
    item = trial_balance_service.get_from_reporting("org", fiscal_period_id="fp1", refresh_if_missing=False)
    assert item["balanced"] is True


# --- pagination cursor ---


def test_trial_balance_repository_cursor_logic() -> None:
    """Verify cursor truncation without DB."""
    rows = [{"account_code": f"{i:04d}"} for i in range(3)]
    limit = 2
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].get("account_code") or "")
    assert len(rows) == 2
    assert next_cursor == "0001"


# --- report events ---


@patch("app.modules.erp.reporting.events.report_events.platform_event_service")
def test_emit_report_generated(mock_pub) -> None:
    from app.modules.erp.reporting.events.report_events import emit_report_generated

    emit_report_generated("org1", report_type="pnl")
    mock_pub.publish.assert_called_once()
    assert mock_pub.publish.call_args.kwargs["event_type"] == "report.generated"


@patch("app.modules.erp.reporting.events.report_events.platform_event_service")
def test_emit_reports_refresh_requested(mock_pub) -> None:
    from app.modules.erp.reporting.events.report_events import emit_reports_refresh_requested

    emit_reports_refresh_requested("org1", reason="daily")
    mock_pub.publish.assert_called_once()


# --- scheduling service ---


@patch("app.modules.platform.events.services.scheduling_service.platform_event_service")
def test_scheduling_emit_reports_daily(mock_pub) -> None:
    from app.modules.platform.events.services.scheduling_service import scheduling_service

    scheduling_service.emit_reports_daily("org1")
    mock_pub.publish.assert_called_once()
    assert mock_pub.publish.call_args.kwargs["event_type"] == "scheduler.reports.daily"


# --- snapshot job ---


@patch("app.modules.erp.reporting.jobs.reporting_snapshot_job.emit_report_snapshot_created")
@patch("app.modules.erp.reporting.jobs.reporting_snapshot_job.snapshots_repository")
@patch("app.modules.erp.reporting.jobs.reporting_snapshot_job.report_engine")
@patch("app.modules.erp.reporting.jobs.reporting_snapshot_job.reporting_schema_repository")
def test_freeze_period_snapshot(mock_schema, mock_engine, mock_snap, mock_emit) -> None:
    from app.modules.erp.reporting.jobs.reporting_snapshot_job import freeze_period_snapshot

    mock_schema.schema_ready.return_value = True
    mock_engine.fetch_payload.return_value = {"sections": []}
    mock_snap.create.return_value = {"id": "snap1"}
    result = freeze_period_snapshot("org", report_type="pnl", period_key="2026-01", filters={"fiscal_period_id": "fp1"})
    assert result["id"] == "snap1"
    mock_emit.assert_called_once()


# --- cleanup job ---


@patch("app.modules.erp.reporting.jobs.report_cleanup_job.report_runs_repository")
@patch("app.modules.erp.reporting.jobs.report_cleanup_job.reporting_schema_repository")
def test_report_cleanup(mock_schema, mock_runs) -> None:
    from app.modules.erp.reporting.jobs.report_cleanup_job import run_cleanup

    mock_schema.schema_ready.return_value = True
    mock_runs.delete_older_than.return_value = 5
    assert run_cleanup("org")["deleted"] == 5


# --- aggregate AP aging (mocked) ---


@patch("app.modules.erp.reporting.engine.aggregation_engine.ap_invoice_repository")
def test_aggregate_ap_aging_buckets(mock_ap) -> None:
    from app.modules.erp.reporting.engine.aggregation_engine import aggregate_ap_aging

    mock_ap.list_outstanding.return_value = [
        {"vendor_id": "v1", "vendor_name": "V", "due_date": "2026-01-01", "outstanding": 100},
        {"vendor_id": "v1", "vendor_name": "V", "due_date": "2025-12-01", "outstanding": 50},
    ]
    rows = aggregate_ap_aging("org", as_of_date="2026-02-01")
    assert len(rows) == 1
    assert rows[0]["total_outstanding"] == 150


# --- date math edge ---


def test_aging_days_future_due() -> None:
    ref = date.today()
    future = (ref + timedelta(days=5)).isoformat()
    assert aging_days(due_date=future, as_of=ref.isoformat()) <= 0
