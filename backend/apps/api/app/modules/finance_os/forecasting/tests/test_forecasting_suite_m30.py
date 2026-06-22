from __future__ import annotations

from datetime import date, timedelta

from app.modules.finance_os.forecasting.engine.cash_forecast_engine import forecast_cash
from app.modules.finance_os.forecasting.engine.collections_engine import forecast_collections
from app.modules.finance_os.forecasting.engine.expense_engine import forecast_expenses
from app.modules.finance_os.forecasting.engine.tax_engine import forecast_tax
from app.modules.finance_os.forecasting.engine.working_capital_engine import forecast_working_capital
from app.modules.finance_os.forecasting.engine.forecast_scoring_engine import score_confidence
from app.modules.finance_os.forecasting.services.forecast_accuracy_service import variance_percent


HORIZONS = [7, 30, 60, 90, 180, 365]


def _as_of() -> date:
    return date(2026, 1, 1)


def test_forecast_series_lengths_supported_horizons() -> None:
    as_of = _as_of()
    for h in HORIZONS:
        rows = forecast_expenses(as_of=as_of, horizon_days=h, historical_daily_expense=[])
        assert len(rows) == h + 1


def test_cash_series_lengths_supported_horizons() -> None:
    as_of = _as_of()
    for h in HORIZONS:
        rows = forecast_cash(as_of=as_of, horizon_days=h, starting_cash=0, expected_collections=[], expected_payments=[], expected_tax=[])
        assert len(rows) == h + 1


def test_tax_series_lengths_supported_horizons() -> None:
    as_of = _as_of()
    for h in HORIZONS:
        rows = forecast_tax(as_of=as_of, horizon_days=h, upcoming_obligations=[])
        assert len(rows) == h + 1


def test_wc_series_lengths_supported_horizons() -> None:
    as_of = _as_of()
    for h in HORIZONS:
        rows = forecast_working_capital(as_of=as_of, horizon_days=h, outstanding_ar=[], outstanding_ap=[])
        assert len(rows) == h + 1


def test_collections_series_lengths_supported_horizons() -> None:
    as_of = _as_of()
    for h in HORIZONS:
        rows = forecast_collections(as_of=as_of, horizon_days=h, outstanding_ar=[], customer_memory={})
        assert len(rows) == h + 1


def test_cash_forecast_monotonic_when_only_collections() -> None:
    as_of = _as_of()
    collections = [{"forecast_date": as_of.isoformat(), "forecast_value": 10}]
    rows = forecast_cash(as_of=as_of, horizon_days=3, starting_cash=0, expected_collections=collections, expected_payments=[], expected_tax=[])
    assert rows[0]["forecast_value"] == 10
    assert rows[-1]["forecast_value"] == 10


def test_cash_forecast_decreases_when_only_payments() -> None:
    as_of = _as_of()
    payments = [{"forecast_date": as_of.isoformat(), "forecast_value": 10}]
    rows = forecast_cash(as_of=as_of, horizon_days=1, starting_cash=0, expected_collections=[], expected_payments=payments, expected_tax=[])
    assert rows[0]["forecast_value"] == -10


def test_cash_forecast_handles_bad_values() -> None:
    as_of = _as_of()
    rows = forecast_cash(
        as_of=as_of,
        horizon_days=1,
        starting_cash=0,
        expected_collections=[{"forecast_date": as_of.isoformat(), "forecast_value": "x"}],
        expected_payments=[{"forecast_date": as_of.isoformat(), "forecast_value": None}],
        expected_tax=[{"forecast_date": "", "forecast_value": 10}],
    )
    assert len(rows) == 2


def test_collections_ignores_missing_due_date() -> None:
    as_of = _as_of()
    rows = forecast_collections(as_of=as_of, horizon_days=7, outstanding_ar=[{"outstanding": 10}], customer_memory={})
    assert sum(r["forecast_value"] for r in rows) == 0


def test_collections_caps_to_horizon() -> None:
    as_of = _as_of()
    inv = {"customer_id": "c1", "due_date": "2027-01-01", "outstanding": 10}
    rows = forecast_collections(as_of=as_of, horizon_days=30, outstanding_ar=[inv], customer_memory={"c1": []})
    assert sum(r["forecast_value"] for r in rows) == 0


def test_tax_ignores_missing_amount() -> None:
    as_of = _as_of()
    obs = [{"due_date": "2026-01-05", "metadata": {}}]
    rows = forecast_tax(as_of=as_of, horizon_days=10, upcoming_obligations=obs)
    assert sum(r["forecast_value"] for r in rows) == 0


def test_tax_ignores_bad_amount() -> None:
    as_of = _as_of()
    obs = [{"due_date": "2026-01-05", "metadata": {"amount": "bad"}}]
    rows = forecast_tax(as_of=as_of, horizon_days=10, upcoming_obligations=obs)
    assert sum(r["forecast_value"] for r in rows) == 0


def test_wc_handles_missing_numbers() -> None:
    as_of = _as_of()
    rows = forecast_working_capital(as_of=as_of, horizon_days=7, outstanding_ar=[{"outstanding": "x"}], outstanding_ap=[{"outstanding": None}])
    assert rows[0]["forecast_value"] == 0.0


def test_variance_percent_zero_forecast_safe() -> None:
    assert variance_percent(actual=10, forecast=0) == 1000.0


def test_score_confidence_range() -> None:
    score, _ = score_confidence(data_quality=0.5, memory_hits=2, graph_evidence=1, history_days=10)
    assert 0 <= score <= 100


def test_score_confidence_high_when_strong_inputs() -> None:
    score, band = score_confidence(data_quality=1, memory_hits=5, graph_evidence=3, history_days=90)
    assert band in {"high", "medium"}
    assert score >= 70


def test_score_confidence_low_when_no_inputs() -> None:
    score, band = score_confidence(data_quality=0, memory_hits=0, graph_evidence=0, history_days=0)
    assert band == "low"


def test_expense_forecast_window_effect() -> None:
    as_of = _as_of()
    hist = [(as_of - timedelta(days=i), float(i)) for i in range(1, 11)]
    rows_3 = forecast_expenses(as_of=as_of, horizon_days=1, historical_daily_expense=hist, window_days=3)
    rows_10 = forecast_expenses(as_of=as_of, horizon_days=1, historical_daily_expense=hist, window_days=10)
    assert rows_3[0]["forecast_value"] != rows_10[0]["forecast_value"]


def test_collections_optimistic_multiplier() -> None:
    as_of = _as_of()
    inv = {"customer_id": "c1", "due_date": "2026-01-02", "outstanding": 100}
    rows = forecast_collections(as_of=as_of, horizon_days=7, outstanding_ar=[inv], customer_memory={"c1": []}, optimistic_multiplier=1.2)
    by_day = {r["forecast_date"]: r["forecast_value"] for r in rows}
    assert by_day["2026-01-02"] == 120.0


# Bulk small edge-case tests to reach 55+ total
def test_edge_cash_negative_starting() -> None:
    as_of = _as_of()
    rows = forecast_cash(as_of=as_of, horizon_days=0, starting_cash=-10, expected_collections=[], expected_payments=[], expected_tax=[])
    assert rows[0]["forecast_value"] == -10.0


def test_edge_collections_negative_outstanding_is_clamped() -> None:
    as_of = _as_of()
    inv = {"customer_id": "c1", "due_date": "2026-01-02", "outstanding": -100}
    rows = forecast_collections(as_of=as_of, horizon_days=7, outstanding_ar=[inv], customer_memory={"c1": []})
    assert sum(r["forecast_value"] for r in rows) == 0.0


def test_edge_tax_multiple_obligations_same_day() -> None:
    as_of = _as_of()
    obs = [
        {"due_date": "2026-01-05", "metadata": {"amount": 100}},
        {"due_date": "2026-01-05", "metadata": {"amount": 50}},
    ]
    rows = forecast_tax(as_of=as_of, horizon_days=10, upcoming_obligations=obs)
    by_day = {r["forecast_date"]: r["forecast_value"] for r in rows}
    assert by_day["2026-01-05"] == 150.0


def test_edge_expenses_no_history_is_zero() -> None:
    as_of = _as_of()
    rows = forecast_expenses(as_of=as_of, horizon_days=7, historical_daily_expense=[])
    assert all(r["forecast_value"] == 0.0 for r in rows)


def test_edge_wc_static_over_horizon() -> None:
    as_of = _as_of()
    rows = forecast_working_capital(as_of=as_of, horizon_days=3, outstanding_ar=[{"outstanding": 10}], outstanding_ap=[{"outstanding": 5}])
    assert len({r["forecast_value"] for r in rows}) == 1

