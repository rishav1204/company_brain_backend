from __future__ import annotations

from app.modules.finance_os.forecasting.repositories.forecast_repository import forecast_repository
from app.modules.finance_os.forecasting.services.forecast_accuracy_service import record_accuracy, variance_percent


def _actual_proxy(org_id: str, *, forecast_type: str, forecast_val: float) -> float:
    try:
        from app.modules.erp.query_services import reporting_queries, treasury_queries

        if forecast_type == "cash":
            pos = treasury_queries.compute_live_position(org_id)
            return float(pos.get("available_cash") or pos.get("net_liquidity") or forecast_val)
        if forecast_type == "collections":
            ar = reporting_queries.get_ar_aging(org_id, refresh_if_missing=False)
            return float((ar.get("totals") or {}).get("grand_total") or forecast_val)
        if forecast_type == "expenses":
            ap = reporting_queries.get_ap_aging(org_id, refresh_if_missing=False)
            return float((ap.get("totals") or {}).get("grand_total") or forecast_val)
    except Exception:
        pass
    return forecast_val


def run_accuracy(org_id: str, *, forecast_type: str = "cash", horizon_days: int = 30) -> dict:
    if not forecast_repository.schema_ready():
        return {"status": "skipped", "reason": "schema_not_ready"}

    rows = forecast_repository.list_latest(org_id, forecast_type=forecast_type, horizon_days=horizon_days, limit=60)
    if not rows:
        return {"status": "ok", "count": 0}

    last = rows[-1]
    fid = str(last.get("id") or "")
    forecast_val = float(last.get("forecast_value") or 0.0)
    actual_val = _actual_proxy(org_id, forecast_type=forecast_type, forecast_val=forecast_val)
    if not fid:
        return {"status": "ok", "count": 0}

    rec = record_accuracy(org_id, forecast_id=fid, actual_value=actual_val, forecast_value=forecast_val)
    return {"status": "ok", "count": 1, "item": rec, "variance_percent": variance_percent(actual=actual_val, forecast=forecast_val)}
