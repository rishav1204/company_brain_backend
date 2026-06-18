from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.accounts_receivable.ai.payment_risk_model import assess_payment_delay_risk
from app.modules.erp.accounts_receivable.engine.collection_engine import collection_probability


def forecast_collections(invoices: list[dict], *, horizons: tuple[int, ...] = (7, 30, 60)) -> dict:
    today = date.today()
    buckets: dict[str, float] = {f"{h}_days": 0.0 for h in horizons}
    at_risk: list[dict] = []
    for inv in invoices:
        if str(inv.get("status")) not in {"issued", "partially_paid", "overdue"}:
            continue
        outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
        if outstanding <= 0:
            continue
        due = date.fromisoformat(str(inv.get("due_date"))[:10])
        risk = assess_payment_delay_risk(inv)
        prob = float(risk.get("collection_probability") or 0.5)
        expected = outstanding * prob
        for h in horizons:
            if due <= today + timedelta(days=h):
                buckets[f"{h}_days"] += expected
        if risk.get("likely_delay"):
            at_risk.append({**risk, "outstanding": outstanding, "due_date": str(inv.get("due_date"))})
    return {
        "forecast": {k: round(v, 2) for k, v in buckets.items()},
        "at_risk_invoices": at_risk,
        "formula": "ExpectedCollections = sum(CollectionProbability × InvoiceAmount)",
    }
