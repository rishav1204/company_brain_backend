from __future__ import annotations

from datetime import date, timedelta


def forecast_cash(
    *,
    as_of: date,
    horizon_days: int,
    starting_cash: float,
    expected_collections: list[dict],
    expected_payments: list[dict],
    expected_tax: list[dict] | None = None,
) -> list[dict]:
    """
    Rule v1: daily cash = prior_cash + collections - payments - taxes.
    Each input list is [{forecast_date, forecast_value}].
    """
    horizon_days = max(1, int(horizon_days))
    cash = float(starting_cash or 0.0)

    def _map(rows: list[dict] | None) -> dict[str, float]:
        out: dict[str, float] = {}
        for r in rows or []:
            d = str(r.get("forecast_date") or "")[:10]
            if not d:
                continue
            try:
                out[d] = out.get(d, 0.0) + float(r.get("forecast_value") or 0.0)
            except (TypeError, ValueError):
                continue
        return out

    coll = _map(expected_collections)
    pay = _map(expected_payments)
    tax = _map(expected_tax or [])

    rows = []
    for i in range(horizon_days + 1):
        d = as_of + timedelta(days=i)
        key = d.isoformat()
        cash = cash + coll.get(key, 0.0) - pay.get(key, 0.0) - tax.get(key, 0.0)
        rows.append({"forecast_date": key, "forecast_value": round(cash, 2)})
    return rows

