from __future__ import annotations

from app.modules.erp.treasury.services.cash_position_service import cash_position_service


class CashPoolService:
    def idle_cash_by_account(self, org_id: str) -> list[dict]:
        position = cash_position_service.compute_live_position(org_id)
        from app.modules.erp.ports.intelligence_registry import intelligence_registry

        accounts = position.get("accounts") or []
        upcoming = float(position.get("upcoming_payments") or 1)
        avg_daily = upcoming / 30 if upcoming > 0 else 10000
        return intelligence_registry.treasury().detect_surplus_cash(
            accounts=accounts,
            avg_daily_outflow=avg_daily,
        )


cash_pool_service = CashPoolService()
