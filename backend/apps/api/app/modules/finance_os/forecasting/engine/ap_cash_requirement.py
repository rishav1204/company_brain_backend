from __future__ import annotations

from datetime import date, timedelta


def forecast_cash_requirement(outstanding_invoices: list[dict], *, horizon_days: int = 30) -> dict:
    horizon_end = date.today() + timedelta(days=horizon_days)
    due_within = []
    total = 0.0
    for inv in outstanding_invoices:
        due = date.fromisoformat(str(inv.get("due_date"))[:10])
        outstanding = float(inv.get("outstanding") or 0)
        if due <= horizon_end and outstanding > 0:
            due_within.append({**inv, "outstanding": outstanding})
            total += outstanding
    return {
        "horizon_days": horizon_days,
        "expected_cash_requirement": round(total, 2),
        "invoices_due": due_within,
        "forecast_date": date.today().isoformat(),
    }
