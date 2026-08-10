from __future__ import annotations

from datetime import date

from app.modules.erp.query_services import domain_calc


def assess_vendor_risk(org_id: str, *, vendor_id: str, invoices: list[dict], payments: list[dict]) -> dict:
    """Analyze payment history, delays, and disputes (simplified risk score)."""
    overdue_count = 0
    paid_late = 0
    disputed = 0
    total_outstanding = 0.0

    today = date.today().isoformat()
    for inv in invoices:
        status = str(inv.get("status"))
        if status in {"approved", "partially_paid"}:
            outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
            total_outstanding += outstanding
            if domain_calc.ap_aging_days(due_date=str(inv.get("due_date")), as_of=today) > 0:
                overdue_count += 1
        meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}
        if meta.get("disputed"):
            disputed += 1

    completed = [p for p in payments if str(p.get("status")) == "completed"]
    failed = [p for p in payments if str(p.get("status")) == "failed"]

    if overdue_count > 2:
        paid_late = overdue_count

    risk_score = min(1.0, (overdue_count * 0.15) + (disputed * 0.2) + (len(failed) * 0.1))
    level = "low"
    if risk_score >= 0.6:
        level = "high"
    elif risk_score >= 0.3:
        level = "medium"

    return {
        "vendor_id": vendor_id,
        "risk_score": round(risk_score, 4),
        "risk_level": level,
        "overdue_invoices": overdue_count,
        "disputed_invoices": disputed,
        "failed_payments": len(failed),
        "completed_payments": len(completed),
        "total_outstanding": round(total_outstanding, 2),
    }
