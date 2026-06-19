from __future__ import annotations

from app.modules.erp.procurement.repositories.policy_repository import policy_repository
from app.modules.erp.procurement.repositories.policy_repository import budget_envelope_repository
from app.modules.erp.procurement.validators.budget_validator import validate_budget_available


class BudgetCheckService:
    def check_pr(self, org_id: str, *, cost_center_id: str | None, amount: float, fiscal_year_id: str | None = None) -> dict:
        policy = policy_repository.get_active(org_id) or {}
        if not policy.get("budget_enforcement") or not cost_center_id:
            return {"sufficient": True, "enforced": False}
        envelope = budget_envelope_repository.get_for_cost_center(
            org_id, cost_center_id=cost_center_id, fiscal_year_id=fiscal_year_id
        )
        if not envelope:
            return {"sufficient": True, "enforced": False, "warning": "no_budget_envelope"}
        result = validate_budget_available(
            allocated=float(envelope.get("allocated") or 0),
            committed=float(envelope.get("committed") or 0),
            consumed=float(envelope.get("consumed") or 0),
            requested=amount,
        )
        result["enforced"] = True
        result["envelope_id"] = envelope.get("id")
        return result

    def commit_spend(self, org_id: str, *, cost_center_id: str | None, amount: float, fiscal_year_id: str | None = None) -> dict | None:
        if not cost_center_id:
            return None
        envelope = budget_envelope_repository.get_for_cost_center(
            org_id, cost_center_id=cost_center_id, fiscal_year_id=fiscal_year_id
        )
        if not envelope:
            return None
        return budget_envelope_repository.commit(org_id, envelope_id=str(envelope["id"]), amount=amount)

    def release_spend(self, org_id: str, *, cost_center_id: str | None, amount: float, fiscal_year_id: str | None = None) -> dict | None:
        if not cost_center_id:
            return None
        envelope = budget_envelope_repository.get_for_cost_center(
            org_id, cost_center_id=cost_center_id, fiscal_year_id=fiscal_year_id
        )
        if not envelope:
            return None
        return budget_envelope_repository.release(org_id, envelope_id=str(envelope["id"]), amount=amount)

    def consume_spend(self, org_id: str, *, cost_center_id: str | None, amount: float, fiscal_year_id: str | None = None) -> dict | None:
        if not cost_center_id:
            return None
        envelope = budget_envelope_repository.get_for_cost_center(
            org_id, cost_center_id=cost_center_id, fiscal_year_id=fiscal_year_id
        )
        if not envelope:
            return None
        return budget_envelope_repository.consume(org_id, envelope_id=str(envelope["id"]), amount=amount)


budget_check_service = BudgetCheckService()
