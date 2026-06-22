from __future__ import annotations

from datetime import date

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.aging_repository import ap_aging_repository, ar_aging_repository
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository


class AgingReportService:
    def get_ap(
        self,
        org_id: str,
        *,
        as_of_date: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
        refresh_if_missing: bool = True,
    ) -> dict:
        as_of = (as_of_date or date.today().isoformat())[:10]
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        lines, next_cursor = ap_aging_repository.list_as_of(org_id, as_of_date=as_of, cursor=cursor, limit=limit)
        totals = ap_aging_repository.totals(org_id, as_of_date=as_of)
        if refresh_if_missing and not lines and float(totals.get("grand_total") or 0) == 0:
            materialization_engine.refresh_ap_aging(org_id, as_of_date=as_of)
            lines, next_cursor = ap_aging_repository.list_as_of(org_id, as_of_date=as_of, cursor=cursor, limit=limit)
            totals = ap_aging_repository.totals(org_id, as_of_date=as_of)
        return {
            "as_of_date": as_of,
            "totals": totals,
            "lines": lines,
            "next_cursor": next_cursor,
            "refreshed_at": totals.get("refreshed_at"),
        }

    def get_ar(
        self,
        org_id: str,
        *,
        as_of_date: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
        refresh_if_missing: bool = True,
    ) -> dict:
        as_of = (as_of_date or date.today().isoformat())[:10]
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        lines, next_cursor = ar_aging_repository.list_as_of(org_id, as_of_date=as_of, cursor=cursor, limit=limit)
        totals = ar_aging_repository.totals(org_id, as_of_date=as_of)
        if refresh_if_missing and not lines and float(totals.get("grand_total") or 0) == 0:
            materialization_engine.refresh_ar_aging(org_id, as_of_date=as_of)
            lines, next_cursor = ar_aging_repository.list_as_of(org_id, as_of_date=as_of, cursor=cursor, limit=limit)
            totals = ar_aging_repository.totals(org_id, as_of_date=as_of)
        return {
            "as_of_date": as_of,
            "totals": totals,
            "lines": lines,
            "next_cursor": next_cursor,
            "refreshed_at": totals.get("refreshed_at"),
        }


aging_report_service = AgingReportService()
