from __future__ import annotations

from app.modules.erp.expenses.repositories.claim_repository import claim_repository


def analyze_spend(org_id: str, *, employee_id: str | None = None) -> dict:
    claims = claim_repository.list(org_id, employee_id=employee_id, limit=500)
    by_type: dict[str, float] = {}
    total = 0.0
    for c in claims:
        amt = float(c.get("total_amount") or 0)
        cat = str(c.get("expense_category") or "uncategorized")
        by_type[cat] = by_type.get(cat, 0) + amt
        total += amt
    return {
        "total_claimed": round(total, 2),
        "claim_count": len(claims),
        "by_category": {k: round(v, 2) for k, v in by_type.items()},
    }
