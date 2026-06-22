from __future__ import annotations

from app.modules.erp.treasury.services.cash_position_service import cash_position_service
from app.modules.erp.treasury.services.liquidity_service import liquidity_service


class TreasuryReportService:
    def cash_position(self, org_id: str) -> dict:
        live = cash_position_service.compute_live_position(org_id)
        history = cash_position_service.history(org_id, limit=30)
        return {"source": "treasury_m24", "position": live, "history": history}

    def liquidity(self, org_id: str) -> dict:
        return liquidity_service.analyze(org_id)


treasury_report_service = TreasuryReportService()
