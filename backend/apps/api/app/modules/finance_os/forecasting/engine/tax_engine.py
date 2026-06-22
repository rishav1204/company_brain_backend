from __future__ import annotations

from datetime import date, timedelta


def forecast_tax(
    *,
    as_of: date,
    horizon_days: int,
    upcoming_obligations: list[dict],
) -> list[dict]:
    """
    Rule v1: allocate compliance obligation `metadata.amount` (if present) on its due_date.
    """
    horizon_days = max(1, int(horizon_days))
    buckets: dict[str, float] = {}
    for ob in upcoming_obligations or []:
        due = str(ob.get("due_date") or "")[:10]
        if not due:
            continue
        meta = ob.get("metadata") if isinstance(ob.get("metadata"), dict) else {}
        amt = meta.get("amount") or meta.get("expected_amount") or 0
        try:
            amt_f = max(0.0, float(amt))
        except (TypeError, ValueError):
            amt_f = 0.0
        if amt_f <= 0:
            continue
        buckets[due] = buckets.get(due, 0.0) + amt_f

    rows = []
    for i in range(horizon_days + 1):
        d = as_of + timedelta(days=i)
        rows.append({"forecast_date": d.isoformat(), "forecast_value": round(buckets.get(d.isoformat(), 0.0), 2)})
    return rows

