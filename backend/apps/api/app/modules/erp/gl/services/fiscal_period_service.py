from __future__ import annotations

from app.modules.erp.gl.repositories.fiscal_period_repository import fiscal_period_repository


class FiscalPeriodService:
    def create(self, org_id: str, *, period_name: str, start_date: str, end_date: str, company_id: str | None = None) -> dict:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        return fiscal_period_repository.create(
            org_id, period_name=period_name, start_date=start_date, end_date=end_date, company_id=company_id
        )

    def list(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return fiscal_period_repository.list(org_id, company_id=company_id)

    def resolve_open_period(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict:
        row = fiscal_period_repository.find_open_for_date(org_id, posting_date=posting_date, company_id=company_id)
        if not row:
            raise ValueError("No fiscal period for posting_date")
        status = str(row.get("status") or "").lower()
        if status not in {"open"} or bool(row.get("is_locked")):
            raise ValueError("Fiscal period is not open")
        return row

    def lock(self, org_id: str, *, fiscal_period_id: str) -> dict:
        item = fiscal_period_repository.set_status(org_id, fiscal_period_id=fiscal_period_id, status="locked", is_locked=True)
        try:
            from app.modules.platform.events.services.event_service import platform_event_service

            platform_event_service.publish(
                event_type="erp.fiscal_period.locked",
                org_id=org_id,
                source="erp.gl",
                entity_type="fiscal_period",
                entity_id=fiscal_period_id,
                payload={"fiscal_period_id": fiscal_period_id, "status": "locked"},
            )
        except Exception:
            pass
        return item

    def close(self, org_id: str, *, fiscal_period_id: str) -> dict:
        item = fiscal_period_repository.set_status(org_id, fiscal_period_id=fiscal_period_id, status="closed", is_locked=True)
        try:
            from app.modules.platform.events.services.event_service import platform_event_service

            platform_event_service.publish(
                event_type="erp.fiscal_period.closed",
                org_id=org_id,
                source="erp.gl",
                entity_type="fiscal_period",
                entity_id=fiscal_period_id,
                payload={"fiscal_period_id": fiscal_period_id, "status": "closed"},
            )
        except Exception:
            pass
        return item


fiscal_period_service = FiscalPeriodService()

