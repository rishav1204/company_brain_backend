from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.statement_repository import pnl_repository
from app.modules.erp.reporting.services.coa_snapshot_reporting import apply_snapshot_to_sections, snapshot_meta


class PnlService:
    def get(
        self,
        org_id: str,
        *,
        fiscal_period_id: str,
        refresh_if_missing: bool = True,
        coa_snapshot: dict | None = None,
    ) -> dict:
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        sections = pnl_repository.list_period(org_id, fiscal_period_id=fiscal_period_id)
        if refresh_if_missing and not sections:
            materialization_engine.refresh_pnl(org_id, fiscal_period_id=fiscal_period_id)
            sections = pnl_repository.list_period(org_id, fiscal_period_id=fiscal_period_id)
        if coa_snapshot:
            sections = apply_snapshot_to_sections(sections, coa_snapshot)
        revenue = sum(float(s.get("amount") or 0) for s in sections if "revenue" in str(s.get("reporting_category", "")).lower())
        expense = sum(float(s.get("amount") or 0) for s in sections if "expense" in str(s.get("reporting_category", "")).lower())
        gross_profit = revenue - expense
        refreshed_at = sections[0].get("refreshed_at") if sections else None
        payload = {
            "fiscal_period_id": fiscal_period_id,
            "sections": sections,
            "refreshed_at": refreshed_at,
            "meta": {
                "revenue_total": round(revenue, 2),
                "expense_total": round(expense, 2),
                "gross_profit": round(gross_profit, 2),
                "net_profit": round(gross_profit, 2),
            },
        }
        if coa_snapshot:
            payload.update(snapshot_meta(coa_snapshot))
        return payload


pnl_service = PnlService()
