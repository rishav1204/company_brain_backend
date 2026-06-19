from __future__ import annotations

from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository
from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service


class FiscalPeriodService:
    def create(self, org_id: str, **fields) -> dict:
        if fields.get("start_date", "") > fields.get("end_date", ""):
            raise ValueError("start_date must be <= end_date")
        return fiscal_period_repository.create(org_id, **fields)

    def list(self, org_id: str, *, fiscal_year_id: str | None = None, company_id: str | None = None) -> list[dict]:
        return fiscal_period_repository.list(org_id, fiscal_year_id=fiscal_year_id, company_id=company_id)

    def get(self, org_id: str, *, period_id: str) -> dict:
        row = fiscal_period_repository.get(org_id, period_id=period_id)
        if not row:
            raise ValueError("Fiscal period not found")
        return row

    def resolve_open_period(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict:
        return posting_validation_service.validate_period_open(org_id, posting_date, company_id=company_id)

    def resolve_period_for_date(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict | None:
        return fiscal_period_repository.find_for_date(org_id, posting_date=posting_date[:10], company_id=company_id)


fiscal_period_service = FiscalPeriodService()
