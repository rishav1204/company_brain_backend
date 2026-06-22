from __future__ import annotations


def evaluate_payment_policy(*, org_id: str | None = None, amount: float, payment_type: str, roles: list[str] | None = None, actor_id: str | None = None) -> dict:
    from app.modules.erp.banking.engine.payment_policy_engine import evaluate_payment_policy as banking_eval

    return banking_eval(org_id=org_id, amount=amount, payment_type=payment_type, roles=roles, actor_id=actor_id)
