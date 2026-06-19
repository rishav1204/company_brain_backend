from __future__ import annotations

from app.modules.erp.expenses.repositories.receipt_repository import advance_repository


class AdvanceService:
    def issue(
        self,
        org_id: str,
        *,
        employee_id: str,
        advance_amount: float,
        issued_date: str | None = None,
        settlement_due_date: str | None = None,
    ) -> dict:
        return advance_repository.create(
            org_id,
            employee_id=employee_id,
            advance_amount=advance_amount,
            issued_date=issued_date,
            settlement_due_date=settlement_due_date,
        )

    def list_open(self, org_id: str, *, employee_id: str) -> list[dict]:
        return advance_repository.list_open(org_id, employee_id=employee_id)

    def settle_against_claim(self, org_id: str, *, employee_id: str, claim_amount: float) -> None:
        remaining = claim_amount
        for adv in advance_repository.list_open(org_id, employee_id=employee_id):
            if remaining <= 0:
                break
            open_amt = float(adv.get("advance_amount") or 0) - float(adv.get("settled_amount") or 0)
            if open_amt <= 0:
                continue
            apply_amt = min(remaining, open_amt)
            advance_repository.adjust(org_id, advance_id=str(adv["id"]), amount=apply_amt)
            remaining -= apply_amt


advance_service = AdvanceService()
