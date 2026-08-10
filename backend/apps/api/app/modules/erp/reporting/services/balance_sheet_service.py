from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.statement_repository import balance_sheet_repository
from app.modules.erp.reporting.services.coa_snapshot_reporting import apply_snapshot_to_sections, snapshot_meta


class BalanceSheetService:
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
        sections = balance_sheet_repository.list_period(org_id, fiscal_period_id=fiscal_period_id)
        if refresh_if_missing and not sections:
            materialization_engine.refresh_balance_sheet(org_id, fiscal_period_id=fiscal_period_id)
            sections = balance_sheet_repository.list_period(org_id, fiscal_period_id=fiscal_period_id)
        if coa_snapshot:
            sections = apply_snapshot_to_sections(sections, coa_snapshot)
        assets = sum(float(s.get("amount") or 0) for s in sections if "asset" in str(s.get("reporting_category", "")).lower())
        liabilities = sum(float(s.get("amount") or 0) for s in sections if "liabilit" in str(s.get("reporting_category", "")).lower())
        equity = sum(float(s.get("amount") or 0) for s in sections if "equity" in str(s.get("reporting_category", "")).lower())
        balanced = round(assets - (liabilities + equity), 2) == 0
        refreshed_at = sections[0].get("refreshed_at") if sections else None
        payload = {
            "fiscal_period_id": fiscal_period_id,
            "sections": sections,
            "refreshed_at": refreshed_at,
            "meta": {
                "assets_total": round(assets, 2),
                "liabilities_total": round(liabilities, 2),
                "equity_total": round(equity, 2),
                "balanced": balanced,
            },
        }
        if coa_snapshot:
            payload.update(snapshot_meta(coa_snapshot))
        return payload


balance_sheet_service = BalanceSheetService()
