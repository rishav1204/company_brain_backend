from __future__ import annotations


class TrialBalanceService:
    """Legacy GL trial balance — delegates to M31 erp_reporting layer."""

    def generate(self, org_id: str, *, fiscal_period_id: str) -> dict:
        try:
            from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service as m31_tb

            item = m31_tb.get_from_reporting(org_id, fiscal_period_id=fiscal_period_id, limit=5000)
            return {
                "fiscal_period_id": item["fiscal_period_id"],
                "totals": item["totals"],
                "balanced": item["balanced"],
                "lines": item["lines"],
            }
        except Exception:
            from app.modules.erp.reporting.engine import materialization_engine
            from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository

            if reporting_schema_repository.schema_ready():
                materialization_engine.refresh_trial_balance(org_id, fiscal_period_id=fiscal_period_id)
                from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service as m31_tb

                item = m31_tb.get_from_reporting(org_id, fiscal_period_id=fiscal_period_id, limit=5000, refresh_if_missing=False)
                return {
                    "fiscal_period_id": item["fiscal_period_id"],
                    "totals": item["totals"],
                    "balanced": item["balanced"],
                    "lines": item["lines"],
                }
            raise


trial_balance_service = TrialBalanceService()
