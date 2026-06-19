from __future__ import annotations


def build_internal_transfer_lines(
    *,
    source_bank_ledger_id: str,
    dest_bank_ledger_id: str,
    amount: float,
) -> list[dict]:
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")
    return [
        {"account_id": dest_bank_ledger_id, "debit_amount": amount, "credit_amount": 0, "line_description": "Internal transfer in"},
        {"account_id": source_bank_ledger_id, "debit_amount": 0, "credit_amount": amount, "line_description": "Internal transfer out"},
    ]


def build_generic_payment_lines(
    *,
    expense_or_liability_account_id: str,
    bank_ledger_account_id: str,
    amount: float,
    description: str = "Treasury payment",
) -> list[dict]:
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    return [
        {"account_id": expense_or_liability_account_id, "debit_amount": amount, "credit_amount": 0, "line_description": description},
        {"account_id": bank_ledger_account_id, "debit_amount": 0, "credit_amount": amount, "line_description": description},
    ]
