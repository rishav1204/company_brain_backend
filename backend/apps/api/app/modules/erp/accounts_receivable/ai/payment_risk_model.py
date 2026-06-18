from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.aging_engine import aging_days
from app.modules.erp.accounts_receivable.engine.collection_engine import collection_probability


def assess_payment_delay_risk(invoice: dict, *, customer_risk_score: float = 0.5) -> dict:
    days = aging_days(due_date=str(invoice.get("due_date")))
    prob = collection_probability(aging_days=max(0, days), risk_score=customer_risk_score)
    likely_delay = prob < 0.6 or days > 0
    return {
        "invoice_id": invoice.get("id"),
        "aging_days": days,
        "collection_probability": prob,
        "likely_delay": likely_delay,
        "risk_level": "high" if likely_delay and days > 30 else ("medium" if likely_delay else "low"),
    }
