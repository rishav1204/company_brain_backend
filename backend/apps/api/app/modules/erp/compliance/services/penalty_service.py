from __future__ import annotations

from app.modules.erp.compliance.engine.penalty_engine import estimate_penalty
from app.modules.erp.compliance.repositories.compliance_repository import (
    compliance_obligation_repository,
    compliance_penalty_repository,
)


class PenaltyService:
    def estimate_for_obligation(self, org_id: str, obligation_id: str) -> dict:
        ob = compliance_obligation_repository.get(org_id, obligation_id)
        if not ob:
            raise ValueError("Obligation not found")
        est = estimate_penalty(obligation=ob, org_id=org_id)
        return compliance_penalty_repository.upsert_estimate(
            org_id,
            obligation_id=obligation_id,
            penalty=float(est["penalty_amount"]),
            interest=float(est["interest_amount"]),
        )

    def refresh_overdue_penalties(self, org_id: str) -> int:
        overdue = compliance_obligation_repository.list(org_id, status="overdue")
        count = 0
        for ob in overdue:
            self.estimate_for_obligation(org_id, ob["id"])
            count += 1
        return count

    def total_exposure(self, org_id: str) -> float:
        return compliance_penalty_repository.total_exposure(org_id)

    def override(self, org_id: str, penalty_id: str, *, penalty_amount: float, interest_amount: float) -> dict:
        return compliance_penalty_repository.override(org_id, penalty_id, penalty_amount=penalty_amount, interest_amount=interest_amount)


penalty_service = PenaltyService()
