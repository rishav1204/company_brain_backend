from __future__ import annotations

from app.modules.erp.treasury.services.cash_position_service import cash_position_service


class TreasuryService:
    def compute_cash_position(self, org_id: str) -> dict:
        return cash_position_service.compute_live_position(org_id)

    def refresh_cash_position(self, org_id: str) -> dict:
        return cash_position_service.refresh_and_emit(org_id)


treasury_service = TreasuryService()
