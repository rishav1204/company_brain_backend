from __future__ import annotations

from app.core.config import settings
from app.modules.erp.fx.repositories.exchange_rate_repository import exchange_rate_repository
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.modules.erp.security.company_scope import require_company_id_for_erp_write


class ExchangeRateService:
    def create_rate(
        self,
        org_id: str,
        *,
        from_currency: str,
        to_currency: str = "INR",
        rate: float,
        rate_date: str,
        source: str = "manual",
        company_id: str | None = None,
    ) -> dict:
        if rate <= 0:
            raise ValueError("Exchange rate must be positive")
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id, company_id=company_id, operation="fx.exchange_rate.create"
            )
        elif company_id:
            require_company_id_for_erp_write(
                org_id=org_id, company_id=company_id, operation="fx.exchange_rate.create"
            )
        return exchange_rate_repository.create(
            org_id,
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            rate_date=rate_date,
            source=source,
            company_id=company_id,
        )

    def get_rate(self, org_id: str, *, rate_id: str) -> dict:
        row = exchange_rate_repository.get(org_id, rate_id=rate_id)
        if not row:
            raise ValueError("Exchange rate not found")
        return row

    def list_rates(
        self,
        org_id: str,
        *,
        from_currency: str | None = None,
        to_currency: str | None = None,
        company_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        return exchange_rate_repository.list(
            org_id,
            from_currency=from_currency,
            to_currency=to_currency,
            company_id=company_id,
            limit=limit,
        )

    def update_rate(
        self,
        org_id: str,
        *,
        rate_id: str,
        rate: float | None = None,
        source: str | None = None,
    ) -> dict:
        if rate is not None and rate <= 0:
            raise ValueError("Exchange rate must be positive")
        row = exchange_rate_repository.update(org_id, rate_id=rate_id, rate=rate, source=source)
        if not row:
            raise ValueError("Exchange rate not found")
        return row

    def delete_rate(self, org_id: str, *, rate_id: str) -> dict:
        if not exchange_rate_repository.delete(org_id, rate_id=rate_id):
            raise ValueError("Exchange rate not found")
        return {"rate_id": rate_id, "deleted": True}

    def resolve_rate(
        self,
        org_id: str,
        *,
        from_currency: str,
        to_currency: str = "INR",
        rate_date: str,
        company_id: str | None = None,
    ) -> dict:
        row = exchange_rate_repository.get_rate_for_date(
            org_id,
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            company_id=company_id,
        )
        if not row:
            raise ValueError(f"No exchange rate for {from_currency}/{to_currency} on or before {rate_date}")
        return row


exchange_rate_service = ExchangeRateService()
