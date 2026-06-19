from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.engine.compliance_engine import calendar_color
from app.modules.erp.compliance.services.obligation_service import obligation_service


class CalendarService:
    def seed_period(self, org_id: str, *, year: int | None = None, month: int | None = None) -> dict:
        today = date.today()
        year = year or today.year
        month = month or today.month
        periods = [f"{year:04d}-{month:02d}"]
        result = obligation_service.generate_for_periods(org_id, periods=periods)
        return {"seeded": result.get("generated", 0), "period": f"{year:04d}-{month:02d}"}

    def list(self, org_id: str, *, status: str | None = None) -> list[dict]:
        legacy_map = {"pending": "upcoming"}
        status = legacy_map.get(status or "", status)
        items = obligation_service.list(org_id, status=status)
        return [self._decorate(i) for i in items]

    def month_view(self, org_id: str, *, year: int, month: int) -> dict:
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        items = obligation_service.list(org_id, from_date=start.isoformat(), to_date=end.isoformat())
        by_date: dict[str, list] = {}
        for item in items:
            d = str(item.get("due_date"))[:10]
            by_date.setdefault(d, []).append(self._decorate(item))
        return {"year": year, "month": month, "by_date": by_date}

    def upcoming(self, org_id: str, *, within_days: int = 7) -> list[dict]:
        return [self._decorate(i) for i in obligation_service.upcoming(org_id, within_days=within_days)]

    def _decorate(self, item: dict) -> dict:
        status = str(item.get("status") or "upcoming")
        return {
            **item,
            "obligation_type": item.get("compliance_code"),
            "color": calendar_color(status),
        }


calendar_service = CalendarService()
