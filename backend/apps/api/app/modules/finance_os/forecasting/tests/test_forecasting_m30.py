from __future__ import annotations

from datetime import date, timedelta

from app.modules.finance_os.forecasting.engine.cash_forecast_engine import forecast_cash
from app.modules.finance_os.forecasting.engine.collections_engine import (
    forecast_collections,
    infer_late_days_from_memory,
)
from app.modules.finance_os.forecasting.engine.expense_engine import forecast_expenses
from app.modules.finance_os.forecasting.engine.tax_engine import forecast_tax
from app.modules.finance_os.forecasting.engine.working_capital_engine import forecast_working_capital
from app.modules.finance_os.forecasting.engine.forecast_scoring_engine import score_confidence
from app.modules.finance_os.forecasting.services.forecast_accuracy_service import variance_percent


def test_infer_late_days_from_memory_parses_days() -> None:
    snippets = [{"content": "Customer usually pays 12 days late"}]
    assert infer_late_days_from_memory(snippets) == 12


def test_infer_late_days_from_memory_default_zero() -> None:
    assert infer_late_days_from_memory([{"content": "no timing info"}]) == 0


def test_forecast_collections_allocates_to_due_date() -> None:
    as_of = date(2026, 1, 1)
    invs = [{"customer_id": "c1", "due_date": "2026-01-03", "outstanding": 1000}]
    rows = forecast_collections(as_of=as_of, horizon_days=7, outstanding_ar=invs, customer_memory={"c1": []})
    by_day = {r["forecast_date"]: r["forecast_value"] for r in rows}
    assert by_day["2026-01-03"] == 1000


def test_forecast_collections_applies_late_days() -> None:
    as_of = date(2026, 1, 1)
    invs = [{"customer_id": "c1", "due_date": "2026-01-03", "outstanding": 1000}]
    mem = {"c1": [{"content": "Pays 5 days late"}]}
    rows = forecast_collections(as_of=as_of, horizon_days=14, outstanding_ar=invs, customer_memory=mem)
    by_day = {r["forecast_date"]: r["forecast_value"] for r in rows}
    assert by_day["2026-01-08"] == 1000


def test_forecast_expenses_returns_baseline() -> None:
    as_of = date(2026, 1, 1)
    hist = [(as_of - timedelta(days=i), 100.0) for i in range(10)]
    rows = forecast_expenses(as_of=as_of, horizon_days=7, historical_daily_expense=hist, window_days=5)
    assert len(rows) == 8
    assert rows[0]["forecast_value"] == 100.0


def test_forecast_tax_allocates_from_metadata() -> None:
    as_of = date(2026, 1, 1)
    obs = [{"due_date": "2026-01-05", "metadata": {"amount": 5000}}]
    rows = forecast_tax(as_of=as_of, horizon_days=10, upcoming_obligations=obs)
    by_day = {r["forecast_date"]: r["forecast_value"] for r in rows}
    assert by_day["2026-01-05"] == 5000


def test_working_capital_proxy_ar_minus_ap() -> None:
    as_of = date(2026, 1, 1)
    ar = [{"outstanding": 1000}]
    ap = [{"outstanding": 250}]
    rows = forecast_working_capital(as_of=as_of, horizon_days=7, outstanding_ar=ar, outstanding_ap=ap)
    assert rows[0]["forecast_value"] == 750.0


def test_cash_forecast_accumulates_daily() -> None:
    as_of = date(2026, 1, 1)
    collections = [{"forecast_date": "2026-01-01", "forecast_value": 100}]
    payments = [{"forecast_date": "2026-01-01", "forecast_value": 40}]
    taxes = [{"forecast_date": "2026-01-01", "forecast_value": 10}]
    rows = forecast_cash(as_of=as_of, horizon_days=1, starting_cash=1000, expected_collections=collections, expected_payments=payments, expected_tax=taxes)
    assert rows[0]["forecast_value"] == 1050.0


def test_score_confidence_bands() -> None:
    s, b = score_confidence(data_quality=1.0, memory_hits=5, graph_evidence=3, history_days=90)
    assert b in {"high", "medium"}
    s2, b2 = score_confidence(data_quality=0.0, memory_hits=0, graph_evidence=0, history_days=0)
    assert b2 == "low"
    assert 0 <= s2 <= 100


def test_variance_percent() -> None:
    assert variance_percent(actual=110, forecast=100) == 10.0

