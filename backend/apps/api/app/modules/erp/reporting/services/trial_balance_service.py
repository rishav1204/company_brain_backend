from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.engine.reporting_cache_engine import is_stale
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.trial_balance_repository import trial_balance_repository


class TrialBalanceService:
    def get_from_reporting(
        self,
        org_id: str,
        *,
        fiscal_period_id: str,
        cursor: str | None = None,
        limit: int = 100,
        refresh_if_missing: bool = True,
    ) -> dict:
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        if refresh_if_missing and not trial_balance_repository.has_data(org_id, fiscal_period_id=fiscal_period_id):
            materialization_engine.refresh_trial_balance(org_id, fiscal_period_id=fiscal_period_id)
        lines, next_cursor = trial_balance_repository.list_period(
            org_id, fiscal_period_id=fiscal_period_id, cursor=cursor, limit=limit
        )
        totals = trial_balance_repository.totals(org_id, fiscal_period_id=fiscal_period_id)
        debit = float(totals.get("debit_total") or 0)
        credit = float(totals.get("credit_total") or 0)
        balanced = round(debit - credit, 2) == 0
        return {
            "fiscal_period_id": fiscal_period_id,
            "totals": {"debit_total": debit, "credit_total": credit},
            "balanced": balanced,
            "lines": lines,
            "next_cursor": next_cursor,
            "refreshed_at": totals.get("refreshed_at"),
        }

    def ensure_fresh(self, org_id: str, *, fiscal_period_id: str, max_age_seconds: float = 3600.0) -> None:
        totals = trial_balance_repository.totals(org_id, fiscal_period_id=fiscal_period_id)
        if not trial_balance_repository.has_data(org_id, fiscal_period_id=fiscal_period_id) or is_stale(
            totals.get("refreshed_at"), max_age_seconds=max_age_seconds
        ):
            materialization_engine.refresh_trial_balance(org_id, fiscal_period_id=fiscal_period_id)


trial_balance_service = TrialBalanceService()
