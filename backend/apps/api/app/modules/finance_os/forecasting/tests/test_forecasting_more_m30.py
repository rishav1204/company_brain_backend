from __future__ import annotations

from datetime import date

from app.modules.finance_os.forecasting.engine.moving_average import simple_moving_average, clamp
from app.modules.finance_os.forecasting.engine.date_math import parse_date, add_days
from app.modules.finance_os.forecasting.ai.forecast_copilot import fallback_explanation
from app.modules.finance_os.forecasting.services.forecast_explanation_service import build_evidence


def test_simple_moving_average_empty() -> None:
    assert simple_moving_average([], 3) == 0.0


def test_simple_moving_average_window() -> None:
    assert simple_moving_average([1, 2, 3, 4], 2) == 3.5


def test_clamp() -> None:
    assert clamp(5, 0, 4) == 4
    assert clamp(-1, 0, 4) == 0


def test_parse_date() -> None:
    assert parse_date("2026-01-02") == date(2026, 1, 2)


def test_add_days() -> None:
    assert add_days(date(2026, 1, 1), 5) == date(2026, 1, 6)


def test_fallback_explanation_contains_range() -> None:
    rows = [{"forecast_date": "2026-01-01", "forecast_value": 10}, {"forecast_date": "2026-01-02", "forecast_value": 11}]
    text = fallback_explanation(forecast_type="cash", rows=rows, evidence={"drivers": ["x"]})
    assert "cash forecast" in text.lower()
    assert "2026-01-01" in text


def test_build_evidence_has_drivers() -> None:
    evidence = build_evidence(inputs={"starting_cash": 1, "ar_outstanding_total": 2, "ap_outstanding_total": 3, "min_cash": 0})
    assert "drivers" in evidence

