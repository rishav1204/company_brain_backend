from __future__ import annotations


def validate_policy_amount(*, amount: float, max_amount: float | None) -> str | None:
    if max_amount is not None and amount > float(max_amount):
        return f"Amount {amount} exceeds policy limit {max_amount}"
    return None


def validate_receipt_required(*, amount: float, receipt_mandatory_above: float, has_receipt: bool) -> str | None:
    if amount > receipt_mandatory_above and not has_receipt:
        return f"Receipt required for amounts above {receipt_mandatory_above}"
    return None
