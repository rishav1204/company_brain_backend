from __future__ import annotations

from datetime import date, timedelta

from app.modules.finance_os.forecasting.engine.moving_average import simple_moving_average


def forecast_expenses(
    *,
    as_of: date,
    horizon_days: int,
    historical_daily_expense: list[tuple[date, float]],
    window_days: int = 30,
) -> list[dict]:
    """
    Rule v1: forecast equals SMA of last N daily expenses.
    """
    horizon_days = max(1, int(horizon_days))
    values = [float(v) for _, v in (historical_daily_expense or []) if v is not None]
    baseline = simple_moving_average(values, window=window_days)
    rows = []
    for i in range(horizon_days + 1):
        d = as_of + timedelta(days=i)
        rows.append({"forecast_date": d.isoformat(), "forecast_value": round(baseline, 2)})
    return rows

