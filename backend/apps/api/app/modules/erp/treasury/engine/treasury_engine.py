from __future__ import annotations


def evaluate_payment_policy(*, amount: float, payment_type: str) -> dict:
    """Treasury policy thresholds (INR). Returns required approval roles."""
    amt = float(amount)
    roles: list[str] = ["treasury_manager"]
    if amt >= 500_000:
        roles.append("cfo")
    if amt >= 2_500_000:
        roles.append("dual_approval")
    if payment_type in {"tax_payment", "internal_transfer"} and amt >= 100_000:
        if "cfo" not in roles:
            roles.append("cfo")
    return {
        "amount": amt,
        "payment_type": payment_type,
        "required_roles": roles,
        "requires_cfo": amt >= 500_000,
        "requires_dual": amt >= 2_500_000,
    }
