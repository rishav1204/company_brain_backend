from __future__ import annotations

from app.modules.finance_os.domain_intelligence.ar.payment_risk_model import assess_payment_delay_risk


def recommend_collections(invoices: list[dict], *, limit: int = 10) -> dict:
    ranked: list[dict] = []
    for inv in invoices:
        if str(inv.get("status")) not in {"issued", "partially_paid", "overdue"}:
            continue
        outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
        if outstanding <= 0:
            continue
        risk = assess_payment_delay_risk(inv)
        if risk.get("likely_delay"):
            ranked.append({
                "invoice_id": inv.get("id"),
                "customer_id": inv.get("customer_id"),
                "outstanding": outstanding,
                "due_date": inv.get("due_date"),
                **risk,
            })
    ranked.sort(key=lambda x: (x.get("aging_days", 0), -x.get("outstanding", 0)), reverse=True)
    top = ranked[:limit]
    return {
        "summary": f"{len(top)} customer invoice(s) likely to delay payment",
        "recommendations": top,
    }
