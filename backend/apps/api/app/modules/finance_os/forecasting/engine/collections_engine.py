from __future__ import annotations

import re
from datetime import date, timedelta

from app.modules.finance_os.forecasting.engine.date_math import add_days, parse_date


_LATE_DAYS_RE = re.compile(r"(\d{1,3})\s*(day|days)\s*(late|delay|delayed)", re.IGNORECASE)


def infer_late_days_from_memory(memory_snippets: list[dict]) -> int:
    for item in memory_snippets or []:
        text = " ".join(str(item.get(k, "")) for k in ("title", "content", "summary", "text"))
        m = _LATE_DAYS_RE.search(text)
        if m:
            try:
                return max(0, min(120, int(m.group(1))))
            except ValueError:
                continue
    return 0


def forecast_collections(
    *,
    as_of: date,
    horizon_days: int,
    outstanding_ar: list[dict],
    customer_memory: dict[str, list[dict]] | None = None,
    optimistic_multiplier: float = 1.0,
) -> list[dict]:
    """
    Rule v1: allocate each invoice outstanding amount on due_date + memory_inferred_late_days.
    """
    horizon_days = max(1, int(horizon_days))
    customer_memory = customer_memory or {}

    buckets: dict[date, float] = {}
    for inv in outstanding_ar or []:
        due_raw = str(inv.get("due_date") or "")[:10]
        if not due_raw:
            continue
        try:
            due = parse_date(due_raw)
        except Exception:
            continue

        customer_id = str(inv.get("customer_id") or "")
        late_days = infer_late_days_from_memory(customer_memory.get(customer_id) or [])
        expected_date = add_days(due, late_days)

        amt = float(inv.get("outstanding") or (float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0)))
        amt = max(0.0, amt) * float(optimistic_multiplier or 1.0)

        if expected_date < as_of:
            expected_date = as_of
        if expected_date > as_of + timedelta(days=horizon_days):
            continue
        buckets[expected_date] = buckets.get(expected_date, 0.0) + amt

    rows = []
    for i in range(horizon_days + 1):
        d = as_of + timedelta(days=i)
        rows.append({"forecast_date": d.isoformat(), "forecast_value": round(buckets.get(d, 0.0), 2)})
    return rows

