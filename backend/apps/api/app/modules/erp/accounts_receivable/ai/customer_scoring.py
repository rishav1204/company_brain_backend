from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.aging_engine import aging_days


def score_customer(*, invoices: list[dict], receipts: list[dict]) -> dict:
    overdue = 0
    disputes = 0
    outstanding = 0.0
    for inv in invoices:
        if str(inv.get("status")) in {"issued", "partially_paid", "overdue"}:
            out = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
            outstanding += out
            if aging_days(due_date=str(inv.get("due_date"))) > 0:
                overdue += 1
        meta = inv.get("metadata") if isinstance(inv.get("metadata"), dict) else {}
        if meta.get("disputed"):
            disputes += 1
    completed = len([r for r in receipts if str(r.get("status")) == "completed"])
    score = min(1.0, overdue * 0.12 + disputes * 0.2 + (outstanding / max(1, outstanding + completed * 10000)) * 0.3)
    level = "low"
    if score >= 0.6:
        level = "high"
    elif score >= 0.3:
        level = "medium"
    return {
        "risk_score": round(score, 4),
        "risk_level": level,
        "overdue_invoices": overdue,
        "disputed_invoices": disputes,
        "total_outstanding": round(outstanding, 2),
    }
