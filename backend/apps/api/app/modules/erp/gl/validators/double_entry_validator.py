from __future__ import annotations


def validate_double_entry(lines: list[dict]) -> tuple[float, float]:
    debit = sum(float(l.get("debit_amount") or 0) for l in lines)
    credit = sum(float(l.get("credit_amount") or 0) for l in lines)
    if round(debit - credit, 2) != 0:
        raise ValueError("Double-entry validation failed: debits != credits")
    return debit, credit

