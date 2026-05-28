from app.services.policy_service import PolicyDecision


def evaluate_amount_limit(attrs: dict | None, amount: float | None) -> PolicyDecision | None:
    if amount is None or not isinstance(attrs, dict):
        return None
    max_amount = attrs.get("max_approve_amount")
    if max_amount is None:
        return None
    try:
        limit = float(max_amount)
    except (TypeError, ValueError):
        return None
    if amount > limit:
        return PolicyDecision(
            allowed=False,
            reason="amount_exceeds_role_abac_limit",
            checks=["abac_amount_limit_denied"],
        )
    return None
