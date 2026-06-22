from __future__ import annotations


def evaluate_payment_policy(
    *,
    org_id: str | None = None,
    amount: float,
    payment_type: str,
    roles: list[str] | None = None,
    actor_id: str | None = None,
) -> dict:
    """Delegate to M34 policy engine — never hardcode thresholds here."""
    if org_id:
        from app.modules.platform.governance.engine import approval_engine
        from app.modules.platform.governance.engine.policy_engine import evaluate

        result = evaluate(
            org_id,
            action="payment.execute",
            attrs={"amount": amount, "payment_type": payment_type},
            roles=roles or [],
            actor_user_id=actor_id,
            dry_run=True,
        )
        return result.to_legacy_payment_policy_dict(amount=amount, payment_type=payment_type)
    from app.modules.platform.governance.engine import approval_engine

    chain = [
        {"level": 1, "role": "finance_manager"},
        {"level": 2, "role": "controller"},
        {"level": 3, "role": "cfo"},
    ]
    return approval_engine.to_legacy_payment_policy(amount, payment_type, chain)
