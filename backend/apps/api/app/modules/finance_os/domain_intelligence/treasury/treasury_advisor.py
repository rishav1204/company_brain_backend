from __future__ import annotations


def advise_treasury(*, liquidity: dict, position: dict) -> list[dict]:
    suggestions = []
    band = liquidity.get("health_band")
    if band == "risk":
        suggestions.append({"action": "delay_non_critical_payments", "detail": "Defer non-essential vendor payments until coverage improves"})
        suggestions.append({"action": "accelerate_collections", "detail": "Prioritize AR follow-up on overdue invoices"})
    elif band == "monitor":
        suggestions.append({"action": "review_upcoming_obligations", "detail": "Review AP and compliance calendar for next 30 days"})
    if float(position.get("available_cash") or 0) > float(position.get("upcoming_payments") or 0) * 2:
        suggestions.append({"action": "optimize_idle_cash", "detail": "Surplus detected — review inter-account transfer or sweep options (advisory)"})
    return suggestions
