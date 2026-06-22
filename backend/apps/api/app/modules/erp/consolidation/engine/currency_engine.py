from __future__ import annotations


def validate_same_currency(currencies: list[str]) -> str | None:
    normalized = {str(c or "INR").upper() for c in currencies if c}
    if not normalized:
        return None
    if len(normalized) > 1:
        return f"Multi-currency consolidation not supported in v1: {sorted(normalized)}"
    return None


def translate_amount(amount: float, *, from_currency: str, to_currency: str, rate: float = 1.0) -> float:
    if str(from_currency).upper() == str(to_currency).upper():
        return float(amount)
    return round(float(amount) * float(rate), 2)
