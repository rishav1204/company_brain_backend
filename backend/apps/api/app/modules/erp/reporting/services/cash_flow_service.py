from __future__ import annotations


class CashFlowService:
    def get(self, org_id: str, *, fiscal_period_id: str | None = None) -> dict:
        return {"status": "phase2", "sections": [], "fiscal_period_id": fiscal_period_id}


cash_flow_service = CashFlowService()
