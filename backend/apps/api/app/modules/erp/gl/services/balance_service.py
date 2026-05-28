from __future__ import annotations

from app.modules.erp.gl.repositories.balance_repository import balance_repository


class BalanceService:
    def list_by_period(self, org_id: str, *, fiscal_period_id: str) -> list[dict]:
        return balance_repository.list_by_period(org_id, fiscal_period_id=fiscal_period_id)

    def recompute_period(self, org_id: str, *, fiscal_period_id: str) -> dict:
        count = balance_repository.recompute_period(org_id, fiscal_period_id=fiscal_period_id)
        return {"fiscal_period_id": fiscal_period_id, "recomputed_rows": count}


balance_service = BalanceService()

