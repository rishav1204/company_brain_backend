from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def priority_score(invoice: dict, *, as_of: str | None = None) -> float:
    """Vendor criticality + due urgency + discount benefit + risk (simplified)."""
    outstanding = float(invoice.get("outstanding") or 0)
    days = domain_calc.ap_aging_days(due_date=str(invoice.get("due_date")), as_of=as_of)
    urgency = min(1.0, max(0.0, days / 90.0))
    discount_rate = float((invoice.get("metadata") or {}).get("early_payment_discount_rate") or 0)
    discount_benefit = domain_calc.compute_discount(
        invoice_amount=outstanding, discount_rate=discount_rate
    ) / max(outstanding, 1)
    vendor_criticality = float((invoice.get("metadata") or {}).get("vendor_criticality") or 0.5)
    return round(urgency * 0.4 + discount_benefit * 0.3 + vendor_criticality * 0.3, 4)


def rank_invoices_for_payment(invoices: list[dict], *, as_of: str | None = None) -> list[dict]:
    ranked = []
    for inv in invoices:
        score = priority_score(inv, as_of=as_of)
        ranked.append({**inv, "priority_score": score})
    return sorted(ranked, key=lambda x: x["priority_score"], reverse=True)
