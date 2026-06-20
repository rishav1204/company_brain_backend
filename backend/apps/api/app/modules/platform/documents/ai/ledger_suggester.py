from __future__ import annotations


def suggest_ledger_accounts(extracted_data: dict, org_id: str | None = None) -> list[dict]:
    """Platform stub — returns M25-style suggestions when org context available."""
    if org_id:
        try:
            from app.modules.finance_os.invoice_ai.retrieval.accounting_patterns import get_accounting_patterns

            vendor = str(extracted_data.get("vendor_name") or extracted_data.get("vendor") or "")
            patterns = get_accounting_patterns(org_id, description=vendor, vendor_name=vendor)
            suggestions = []
            for p in patterns[:3]:
                meta = p.get("metadata") or {}
                suggestions.append(
                    {
                        "account_code": meta.get("account_code", "5000"),
                        "account_name": meta.get("account_name", "Expense"),
                        "confidence": float(p.get("score") or 0.5),
                    }
                )
            if suggestions:
                return suggestions
        except Exception:
            pass

    total = float(extracted_data.get("total_amount") or 0)
    if total <= 0:
        return []
    return [
        {"account_code": "2100", "account_name": "Input GST", "confidence": 0.68},
        {"account_code": "5000", "account_name": "Accounts Payable", "confidence": 0.72},
    ]
