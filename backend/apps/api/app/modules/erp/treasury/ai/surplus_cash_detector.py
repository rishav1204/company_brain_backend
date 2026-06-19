from __future__ import annotations


def detect_surplus_cash(*, accounts: list[dict], avg_daily_outflow: float) -> list[dict]:
    suggestions = []
    threshold = max(avg_daily_outflow * 14, 100000)
    for acct in accounts:
        avail = float(acct.get("available") or 0)
        if avail > threshold:
            suggestions.append({
                "bank_account_id": acct.get("bank_account_id"),
                "account_name": acct.get("account_name"),
                "idle_amount": round(avail - threshold, 2),
                "recommendation": "Consider sweep to treasury account or short-term investment (advisory only)",
            })
    return suggestions
