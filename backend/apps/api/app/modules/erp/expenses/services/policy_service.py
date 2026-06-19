from __future__ import annotations

from app.modules.erp.expenses.repositories.receipt_repository import policy_repository
from app.modules.erp.expenses.validators.policy_validator import validate_policy_amount, validate_receipt_required
from app.modules.erp.expenses.events.expense_events import emit_policy_violation


class ExpensePolicyService:
    def list_policies(self, org_id: str) -> list[dict]:
        return policy_repository.list_all(org_id)

    def validate_item(
        self,
        org_id: str,
        *,
        claim_id: str,
        expense_type: str,
        amount: float,
        has_receipt: bool,
        record: bool = True,
    ) -> list[dict]:
        violations: list[dict] = []
        policies = policy_repository.list_active(org_id, expense_type=expense_type)
        if not policies:
            policies = policy_repository.list_active(org_id, expense_type="miscellaneous")
        for policy in policies:
            msg = validate_policy_amount(amount=amount, max_amount=policy.get("max_amount"))
            if msg:
                v = {"violation_type": "amount_limit", "severity": "error", "message": msg, "policy_id": policy.get("id")}
                violations.append(v)
                if record:
                    policy_repository.record_violation(
                        org_id, claim_id=claim_id, policy_id=policy.get("id"),
                        violation_type="amount_limit", severity="error", message=msg,
                    )
                    emit_policy_violation(org_id, claim_id=claim_id, violation_type="amount_limit", message=msg)
            msg2 = validate_receipt_required(
                amount=amount,
                receipt_mandatory_above=float(policy.get("receipt_mandatory_above") or 500),
                has_receipt=has_receipt,
            )
            if msg2:
                v = {"violation_type": "receipt_required", "severity": "error", "message": msg2, "policy_id": policy.get("id")}
                violations.append(v)
                if record:
                    policy_repository.record_violation(
                        org_id, claim_id=claim_id, policy_id=policy.get("id"),
                        violation_type="receipt_required", severity="error", message=msg2,
                    )
                    emit_policy_violation(org_id, claim_id=claim_id, violation_type="receipt_required", message=msg2)
        return violations

    def validate_claim(self, org_id: str, *, claim_id: str, items: list[dict]) -> list[dict]:
        all_v: list[dict] = []
        for item in items:
            all_v.extend(
                self.validate_item(
                    org_id,
                    claim_id=claim_id,
                    expense_type=str(item.get("expense_type") or "miscellaneous"),
                    amount=float(item.get("amount") or 0),
                    has_receipt=bool(item.get("receipt_id")),
                    record=False,
                )
            )
        if all_v and items:
            for v in all_v:
                policy_repository.record_violation(
                    org_id, claim_id=claim_id, policy_id=v.get("policy_id"),
                    violation_type=v["violation_type"], severity=v["severity"], message=v["message"],
                )
                emit_policy_violation(org_id, claim_id=claim_id, violation_type=v["violation_type"], message=v["message"])
        return all_v


expense_policy_service = ExpensePolicyService()
