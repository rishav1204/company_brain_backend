from __future__ import annotations

from datetime import date, timedelta


STANDARD_HORIZONS = (7, 30, 60, 90, 180)


def forecast_balance(
    *,
    current_closing: float,
    inflows: list[dict],
    outflows: list[dict],
    horizon_days: int,
    as_of: date | None = None,
) -> dict:
    today = as_of or date.today()
    end = today + timedelta(days=horizon_days)
    total_in = 0.0
    total_out = 0.0
    for item in inflows:
        d = date.fromisoformat(str(item.get("date") or item.get("due_date") or today)[:10])
        if today <= d <= end:
            total_in += float(item.get("amount") or 0)
    for item in outflows:
        d = date.fromisoformat(str(item.get("date") or item.get("due_date") or today)[:10])
        if today <= d <= end:
            total_out += float(item.get("amount") or 0)
    balance = round(current_closing + total_in - total_out, 2)
    sources = {str(i.get("source") or "unknown") for i in inflows + outflows}
    confidence = min(100.0, round(40 + len(sources) * 12, 2))
    return {
        "horizon_days": horizon_days,
        "forecast_date": today.isoformat(),
        "expected_inflows": round(total_in, 2),
        "expected_outflows": round(total_out, 2),
        "forecast_cash_balance": balance,
        "confidence_score": confidence,
    }


def forecast_all_horizons(*, current_closing: float, inflows: list[dict], outflows: list[dict]) -> list[dict]:
    return [
        forecast_balance(current_closing=current_closing, inflows=inflows, outflows=outflows, horizon_days=h)
        for h in STANDARD_HORIZONS
    ]
