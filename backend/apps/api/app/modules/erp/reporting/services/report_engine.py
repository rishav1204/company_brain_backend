from __future__ import annotations

from app.modules.erp.reporting.services.aging_report_service import aging_report_service
from app.modules.erp.reporting.services.balance_sheet_service import balance_sheet_service
from app.modules.erp.reporting.services.forecast_report_service import forecast_report_service
from app.modules.erp.reporting.services.gst_report_service import gst_report_service
from app.modules.erp.reporting.services.pnl_service import pnl_service
from app.modules.erp.reporting.services.tds_report_service import tds_report_service
from app.modules.erp.reporting.services.treasury_report_service import treasury_report_service
from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service

_SYNC_THRESHOLD = 5000


class ReportEngine:
    def should_async(self, report_type: str, *, row_count: int = 0) -> bool:
        if report_type in {"gst", "tds"} and row_count > 100:
            return True
        return row_count > _SYNC_THRESHOLD

    def fetch_payload(self, org_id: str, *, report_type: str, filters: dict) -> dict:
        rt = report_type.lower()
        if rt == "trial_balance":
            return trial_balance_service.get_from_reporting(
                org_id,
                fiscal_period_id=str(filters["fiscal_period_id"]),
                limit=int(filters.get("limit") or 5000),
            )
        if rt == "pnl":
            return pnl_service.get(org_id, fiscal_period_id=str(filters["fiscal_period_id"]))
        if rt == "balance_sheet":
            return balance_sheet_service.get(org_id, fiscal_period_id=str(filters["fiscal_period_id"]))
        if rt == "ap_aging":
            return aging_report_service.get_ap(org_id, as_of_date=filters.get("as_of_date"), limit=5000)
        if rt == "ar_aging":
            return aging_report_service.get_ar(org_id, as_of_date=filters.get("as_of_date"), limit=5000)
        if rt == "gst":
            return gst_report_service.get(
                org_id,
                return_period=str(filters["return_period"]),
                return_type=str(filters.get("return_type") or "GSTR-3B"),
            )
        if rt == "tds":
            return tds_report_service.get(
                org_id,
                return_period=str(filters["return_period"]),
                form_type=str(filters.get("form_type") or "26Q"),
            )
        if rt == "treasury_cash":
            return treasury_report_service.cash_position(org_id)
        if rt.startswith("forecast"):
            return forecast_report_service.get(
                org_id,
                forecast_type=str(filters.get("forecast_type") or "cash"),
                horizon_days=int(filters.get("horizon_days") or 30),
                as_of_date=filters.get("as_of_date"),
            )
        raise ValueError(f"Unsupported report type: {report_type}")


report_engine = ReportEngine()
