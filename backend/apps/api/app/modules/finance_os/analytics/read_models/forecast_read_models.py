from __future__ import annotations


def load_forecast(org_id: str, *, forecast_type: str = "cash", horizon_days: int = 30) -> dict:
    from app.modules.finance_os.forecasting.services.forecast_query_service import get_series

    series = get_series(org_id, forecast_type=forecast_type, horizon_days=horizon_days)
    items = series.get("items") or []
    avg_forecast = sum(float(i.get("forecast_value") or 0) for i in items) / max(len(items), 1)
    return {
        "forecast_type": forecast_type,
        "horizon_days": horizon_days,
        "items": items,
        "avg_daily_forecast": avg_forecast,
        "confidence_band": series.get("confidence_band"),
    }


def load_forecast_accuracy(org_id: str) -> dict:
    try:
        from app.modules.finance_os.forecasting.services.forecast_accuracy_query_service import list_org_accuracy

        rows = list_org_accuracy(org_id, limit=100)
    except Exception:
        rows = []
    if not rows:
        return {"accuracy_avg": None, "rows": []}
    avg = sum(abs(float(r.get("variance_percent") or 0)) for r in rows) / len(rows)
    return {"accuracy_avg": round(avg, 2), "rows": rows}
