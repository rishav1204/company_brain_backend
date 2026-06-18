from __future__ import annotations


def build_receipt_journal_lines(*, bank_account_id: str, receivable_account_id: str, amount: float) -> list[dict]:
    """Customer payment: Bank Dr + Accounts Receivable Cr"""
    return [
        {
            "account_id": bank_account_id,
            "debit_amount": amount,
            "credit_amount": 0,
            "line_description": "Customer receipt",
        },
        {
            "account_id": receivable_account_id,
            "debit_amount": 0,
            "credit_amount": amount,
            "line_description": "Receivable settlement",
        },
    ]


def collection_probability(*, aging_days: int, risk_score: float) -> float:
    """Simplified collection probability for cash forecast."""
    base = max(0.1, 1.0 - (aging_days / 180.0))
    return round(min(0.99, base * (1.0 - risk_score * 0.5)), 4)
