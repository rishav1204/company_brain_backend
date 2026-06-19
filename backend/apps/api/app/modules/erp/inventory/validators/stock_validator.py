from __future__ import annotations


def validate_receipt(*, quantity: float, unit_cost: float) -> None:
    if quantity <= 0:
        raise ValueError("Receipt quantity must be positive")
    if unit_cost < 0:
        raise ValueError("Unit cost cannot be negative")


def validate_issue(*, quantity: float) -> None:
    if quantity <= 0:
        raise ValueError("Issue quantity must be positive")


def validate_adjustment(*, quantity_variance: float) -> None:
    if quantity_variance == 0:
        raise ValueError("Adjustment quantity variance cannot be zero")
