from __future__ import annotations


def validate_adjustment(*, adjustment_type: str, amount: float, expense_account_id: str | None, bank_account_id: str | None) -> None:
    if adjustment_type not in {"bank_charge", "fx_difference", "rounding"}:
        raise ValueError("Invalid adjustment type")
    if amount <= 0:
        raise ValueError("Adjustment amount must be positive")
    if not expense_account_id:
        raise ValueError("expense_account_id required for adjustment journal")
    if not bank_account_id:
        raise ValueError("bank_account_id required for adjustment journal")
