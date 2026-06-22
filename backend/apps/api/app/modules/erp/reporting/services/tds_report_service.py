from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.tax_summary_repository import tds_summary_repository


class TdsReportService:
    def get(
        self,
        org_id: str,
        *,
        return_period: str,
        form_type: str = "26Q",
        refresh_if_missing: bool = True,
    ) -> dict:
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        row = tds_summary_repository.get(org_id, return_period=return_period, type_value=form_type)
        if refresh_if_missing and not row:
            materialization_engine.refresh_tds_summary(org_id, return_period=return_period, form_type=form_type)
            row = tds_summary_repository.get(org_id, return_period=return_period, type_value=form_type)
        if not row:
            return {"return_period": return_period, "type_value": form_type, "payload": {}, "refreshed_at": None}
        return row


tds_report_service = TdsReportService()
