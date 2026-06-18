from __future__ import annotations


def available_credit(*, credit_limit: float, outstanding: float) -> float:
    return round(max(0.0, float(credit_limit) - float(outstanding)), 2)


def credit_check(*, credit_limit: float, outstanding: float, invoice_amount: float) -> dict:
    available = available_credit(credit_limit=credit_limit, outstanding=outstanding)
    exceeds = float(invoice_amount) > available
    return {
        "credit_limit": credit_limit,
        "outstanding_receivable": outstanding,
        "available_credit": available,
        "invoice_amount": invoice_amount,
        "exceeds_limit": exceeds,
        "requires_approval": exceeds and credit_limit > 0,
        "block": exceeds and credit_limit <= 0,
    }
