from __future__ import annotations

from app.modules.erp.treasury.engine.treasury_engine import evaluate_payment_policy


class TreasuryPolicyService:
    def check_payment(self, *, org_id: str, amount: float, payment_type: str, roles: list[str] | None = None) -> dict:
        policy = evaluate_payment_policy(org_id=org_id, amount=amount, payment_type=payment_type, roles=roles)
        user_roles = {r.lower() for r in (roles or [])}
        missing = [r for r in policy["required_roles"] if r not in user_roles and "finance_admin" not in user_roles]
        policy["allowed"] = len(missing) == 0 or "finance_admin" in user_roles or "*" in user_roles
        policy["missing_roles"] = missing
        return policy


treasury_policy_service = TreasuryPolicyService()
