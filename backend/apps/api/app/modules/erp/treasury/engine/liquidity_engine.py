from __future__ import annotations

from datetime import date, timedelta


BUCKETS = (0, 7, 30, 90, 180)


def bucket_cashflows(
    *,
    inflows: list[dict],
    outflows: list[dict],
    as_of: date | None = None,
) -> dict:
    today = as_of or date.today()
    buckets: dict[str, dict] = {}
    for days in BUCKETS:
        label = "today" if days == 0 else f"{days}d"
        end = today + timedelta(days=days)
        bucket_in = 0.0
        bucket_out = 0.0
        for item in inflows:
            d = date.fromisoformat(str(item.get("due_date") or item.get("date") or today)[:10])
            if d <= end:
                bucket_in += float(item.get("amount") or 0)
        for item in outflows:
            d = date.fromisoformat(str(item.get("due_date") or item.get("date") or today)[:10])
            if d <= end:
                bucket_out += float(item.get("amount") or 0)
        buckets[label] = {
            "horizon_days": days,
            "inflows": round(bucket_in, 2),
            "outflows": round(bucket_out, 2),
            "net": round(bucket_in - bucket_out, 2),
        }
    return {"as_of": today.isoformat(), "buckets": buckets}


def compute_coverage_ratio(*, available_cash: float, total_obligations: float) -> float:
    if total_obligations <= 0:
        return 999.0 if available_cash > 0 else 0.0
    return round(float(available_cash) / float(total_obligations), 4)
