from __future__ import annotations


def classify_velocity(*, issue_count_30d: int, issue_count_90d: int) -> str:
    if issue_count_30d >= 10:
        return "fast_moving"
    if issue_count_90d >= 5:
        return "normal"
    if issue_count_90d > 0:
        return "slow_moving"
    return "non_moving"


def detect_stock_risk(balances: list[dict], *, reorder_days: int = 14) -> list[dict]:
    risks = []
    for b in balances:
        qty = float(b.get("quantity_on_hand") or 0)
        if qty <= 0:
            risks.append({"item_id": b.get("item_id"), "risk": "stockout", "quantity": qty})
        elif qty < reorder_days:
            risks.append({"item_id": b.get("item_id"), "risk": "low_stock", "quantity": qty})
    return risks
