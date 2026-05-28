from __future__ import annotations


def suggest_ledger_accounts(extracted_data: dict) -> list[dict]:
    total = float(extracted_data.get("total_amount") or 0)
    if total <= 0:
        return []
    # Phase 8: if COA exists, we can suggest canonical accounts by code.
    # This function MUST remain suggestion-only (never auto-post).
    suggestions = [
        {"account_code": "2100", "account_name": "Input GST", "confidence": 0.68},
        {"account_code": "5000", "account_name": "Accounts Payable", "confidence": 0.72},
    ]
    return suggestions
