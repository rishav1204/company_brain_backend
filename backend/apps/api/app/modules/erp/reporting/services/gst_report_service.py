from __future__ import annotations

from app.modules.erp.reporting.engine import materialization_engine
from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
from app.modules.erp.reporting.repositories.tax_summary_repository import gst_summary_repository


class GstReportService:
    def get(
        self,
        org_id: str,
        *,
        return_period: str,
        return_type: str = "GSTR-3B",
        refresh_if_missing: bool = True,
    ) -> dict:
        if not reporting_schema_repository.schema_ready():
            raise ValueError("erp_reporting schema not ready")
        row = gst_summary_repository.get(org_id, return_period=return_period, type_value=return_type)
        if refresh_if_missing and not row:
            materialization_engine.refresh_gst_summary(org_id, return_period=return_period, return_type=return_type)
            row = gst_summary_repository.get(org_id, return_period=return_period, type_value=return_type)
        if not row:
            return {"return_period": return_period, "type_value": return_type, "payload": {}, "refreshed_at": None}
        return row


gst_report_service = GstReportService()
