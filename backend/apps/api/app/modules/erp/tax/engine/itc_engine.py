from __future__ import annotations


def evaluate_itc_eligibility(
    *,
    itc_type: str,
    amount: float,
    blocked_rules: list[dict],
    itc_eligible_mapping: bool = True,
    expense_category: str | None = None,
) -> dict:
    if not itc_eligible_mapping:
        return {"status": "ineligible", "eligible_amount": 0.0, "blocked_amount": amount}
    blocked_pct = 0.0
    for rule in blocked_rules:
        if not rule.get("is_active", True):
            continue
        cat = str(rule.get("category") or "").lower()
        if expense_category and cat and cat in expense_category.lower():
            blocked_pct = max(blocked_pct, float(rule.get("block_percentage") or 100))
    if blocked_pct >= 100:
        return {"status": "blocked", "eligible_amount": 0.0, "blocked_amount": amount}
    if blocked_pct > 0:
        blocked = round(amount * blocked_pct / 100, 2)
        return {
            "status": "partially_eligible",
            "eligible_amount": round(amount - blocked, 2),
            "blocked_amount": blocked,
            "itc_type": itc_type,
        }
    return {"status": "eligible", "eligible_amount": amount, "blocked_amount": 0.0, "itc_type": itc_type}


def build_itc_rows(gst_transaction: dict, eligibility_rows: list[dict]) -> list[dict]:
    rows = []
    for el in eligibility_rows:
        rows.append({
            "itc_type": el.get("itc_type"),
            "eligible_amount": el.get("eligible_amount", 0),
            "claimed_amount": 0.0,
            "status": el.get("status", "eligible"),
            "metadata": {"blocked_amount": el.get("blocked_amount", 0)},
        })
    return rows
