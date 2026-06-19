from __future__ import annotations

from app.modules.erp.tax.services.gst_return_service import gst_return_service
from app.modules.erp.tax.services.tds_return_service import tds_return_service


class FilingService:
    """Unified filing facade for GST and TDS compliance workflows."""

    def generate_gst_return(self, org_id: str, *, return_type: str, return_period: str) -> dict:
        return gst_return_service.generate_return(org_id, return_type=return_type, return_period=return_period)

    def file_gst_return(self, org_id: str, *, return_id: str, filed_by: str) -> dict:
        return gst_return_service.file_return(org_id, return_id=return_id, filed_by=filed_by)

    def generate_tds_return(self, org_id: str, *, return_period: str, form_type: str = "26Q") -> dict:
        return tds_return_service.generate_return(org_id, return_period=return_period, form_type=form_type)

    def file_tds_return(self, org_id: str, *, return_id: str, filed_by: str) -> dict:
        return tds_return_service.file_return(org_id, return_id=return_id, filed_by=filed_by)


filing_service = FilingService()
