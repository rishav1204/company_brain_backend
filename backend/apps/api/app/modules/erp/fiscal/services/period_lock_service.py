from __future__ import annotations

from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository


class PeriodLockService:
    def soft_lock(self, org_id: str, *, period_id: str, actor_id: str | None = None) -> dict:
        return fiscal_period_repository.set_lock_status(org_id, period_id=period_id, lock_status="soft_locked")

    def hard_lock(self, org_id: str, *, period_id: str, actor_id: str | None = None) -> dict:
        return fiscal_period_repository.set_lock_status(org_id, period_id=period_id, lock_status="hard_locked")

    def close(self, org_id: str, *, period_id: str, closed_by: str | None = None) -> dict:
        return fiscal_period_repository.set_lock_status(
            org_id, period_id=period_id, lock_status="closed", closed_by=closed_by
        )

    def reopen(self, org_id: str, *, period_id: str) -> dict:
        return fiscal_period_repository.set_lock_status(org_id, period_id=period_id, lock_status="open")


period_lock_service = PeriodLockService()
