from __future__ import annotations

from datetime import date

from app.modules.erp.compliance.services.calendar_service import calendar_service
from app.modules.erp.compliance.services.compliance_scheduler_service import compliance_scheduler_service


class ComplianceCalendarService:
    """Thin facade — M21 owns regulatory obligations; tax routes remain backward-compatible aliases."""

    def seed_period(self, org_id: str, *, year: int | None = None, month: int | None = None) -> dict:
        return calendar_service.seed_period(org_id, year=year, month=month)

    def list_obligations(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return calendar_service.list(org_id, status=status)

    def check_upcoming(self, org_id: str, *, within_days: int = 7) -> list[dict]:
        return calendar_service.upcoming(org_id, within_days=within_days)

    def run_daily_scan(self, org_id: str) -> dict:
        return compliance_scheduler_service.run_daily(org_id)


compliance_calendar_service = ComplianceCalendarService()
