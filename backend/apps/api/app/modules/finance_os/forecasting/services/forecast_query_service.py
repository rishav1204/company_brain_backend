from __future__ import annotations

from app.modules.finance_os.forecasting.repositories.explanation_repository import explanation_repository
from app.modules.finance_os.forecasting.repositories.forecast_repository import forecast_repository


def get_series(
    org_id: str,
    *,
    forecast_type: str,
    horizon_days: int,
    as_of_date: str | None = None,
) -> dict:
    rows = forecast_repository.list_latest(org_id, forecast_type=forecast_type, horizon_days=horizon_days, as_of_date=as_of_date)
    if not rows:
        return {"items": [], "confidence_score": 0.0, "confidence_band": "low", "as_of_date": as_of_date or ""}
    first = rows[0]
    fid = str(first.get("id") or "")
    expl = explanation_repository.get_latest_for_forecast(org_id, forecast_id=fid) if fid else None
    return {
        "items": [{"forecast_date": r["forecast_date"], "forecast_value": float(r["forecast_value"])} for r in rows],
        "confidence_score": float(first.get("confidence_score") or 0.0),
        "confidence_band": str(first.get("confidence_band") or "low"),
        "as_of_date": str(first.get("as_of_date") or as_of_date or ""),
        "explanation": (expl or {}).get("explanation") if expl else None,
        "evidence": (expl or {}).get("evidence") if expl else {},
    }

