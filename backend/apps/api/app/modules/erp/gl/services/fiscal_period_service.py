from __future__ import annotations

from app.modules.erp.fiscal.services.close_service import close_service
from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service as erp_fiscal_period_service
from app.modules.erp.fiscal.events.period_events import emit_period_hard_locked


class FiscalPeriodService:
    """Backward-compatible facade; canonical logic lives in erp.fiscal."""

    def create(self, org_id: str, *, period_name: str, start_date: str, end_date: str, company_id: str | None = None) -> dict:
        return erp_fiscal_period_service.create(
            org_id,
            period_name=period_name,
            start_date=start_date,
            end_date=end_date,
            company_id=company_id,
        )

    def list(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return erp_fiscal_period_service.list(org_id, company_id=company_id)

    def resolve_open_period(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict:
        return erp_fiscal_period_service.resolve_open_period(org_id, posting_date=posting_date, company_id=company_id)

    def lock(self, org_id: str, *, fiscal_period_id: str) -> dict:
        return close_service.lock_legacy(org_id, period_id=fiscal_period_id)

    def close(self, org_id: str, *, fiscal_period_id: str) -> dict:
        return close_service.close_legacy(org_id, period_id=fiscal_period_id, actor_id="system")


fiscal_period_service = FiscalPeriodService()
