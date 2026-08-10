from __future__ import annotations

from datetime import date, timedelta


def forecast_cashflow(*, inflows: list[dict], outflows: list[dict], horizon_days: int = 30) -> dict:
    end = date.today() + timedelta(days=horizon_days)
    total_in = sum(
        float(i.get("amount") or 0)
        for i in inflows
        if date.fromisoformat(str(i.get("date") or date.today())[:10]) <= end
    )
    total_out = sum(
        float(o.get("amount") or 0)
        for o in outflows
        if date.fromisoformat(str(o.get("date") or date.today())[:10]) <= end
    )
    return {
        "horizon_days": horizon_days,
        "forecast_date": date.today().isoformat(),
        "projected_inflows": round(total_in, 2),
        "projected_outflows": round(total_out, 2),
        "net_cashflow": round(total_in - total_out, 2),
    }
