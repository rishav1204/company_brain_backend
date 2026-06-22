from __future__ import annotations

from datetime import date, timedelta


def forecast_working_capital(
    *,
    as_of: date,
    horizon_days: int,
    outstanding_ar: list[dict],
    outstanding_ap: list[dict],
) -> list[dict]:
    """
    Rule v1: WC proxy = AR_outstanding - AP_outstanding (static), repeated across horizon.
    """
    horizon_days = max(1, int(horizon_days))
    ar_total = 0.0
    for inv in outstanding_ar or []:
        try:
            ar_total += float(inv.get("outstanding") or (float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0)))
        except (TypeError, ValueError):
            continue
    ap_total = 0.0
    for inv in outstanding_ap or []:
        try:
            ap_total += float(inv.get("outstanding") or (float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0)))
        except (TypeError, ValueError):
            continue
    wc = round(ar_total - ap_total, 2)
    rows = []
    for i in range(horizon_days + 1):
        d = as_of + timedelta(days=i)
        rows.append({"forecast_date": d.isoformat(), "forecast_value": wc})
    return rows

