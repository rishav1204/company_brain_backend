from __future__ import annotations


def check_negative_stock(*, qty_after: float, rule: str) -> None:
    if qty_after >= -0.0001:
        return
    rule = str(rule or "block").lower()
    if rule == "allow":
        return
    if rule == "warn":
        return
    raise ValueError("Negative stock not allowed")


def transfer_quantities(*, qty: float) -> tuple[float, float]:
    if qty <= 0:
        raise ValueError("Transfer quantity must be positive")
    return -qty, qty
