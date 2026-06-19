from __future__ import annotations

from app.modules.erp.tax.engine.tds_engine import financial_year_from_date, quarter_from_date
from app.modules.erp.tax.events.tax_events import emit_compliance_alert
from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository
from app.modules.erp.tax.repositories.tds_challan_repository import tds_challan_repository


class TdsChallanService:
    def create_challan(
        self,
        org_id: str,
        *,
        amount: float,
        deposit_date: str | None = None,
        bsr_code: str | None = None,
        cin: str | None = None,
        challan_no: str | None = None,
        quarter: str | None = None,
        financial_year: str | None = None,
        transaction_ids: list[str] | None = None,
        tax_type: str = "TDS",
    ) -> dict:
        ref_date = deposit_date or str(__import__("datetime").date.today())
        row = tds_challan_repository.create(
            org_id,
            tax_type=tax_type,
            amount=amount,
            deposit_date=deposit_date,
            bsr_code=bsr_code,
            cin=cin,
            challan_no=challan_no,
            quarter=quarter or quarter_from_date(ref_date),
            financial_year=financial_year or financial_year_from_date(ref_date),
            status="pending",
        )
        cid = str(row["id"])
        if transaction_ids:
            tds_transaction_repository.link_challan(org_id, transaction_ids=transaction_ids, challan_id=cid)
        emit_compliance_alert(org_id, alert_type="tds.challan.created", summary=f"TDS challan created for ₹{amount:,.2f}")
        return tds_challan_repository.get(org_id, challan_id=cid) or row

    def mark_paid(
        self,
        org_id: str,
        *,
        challan_id: str,
        challan_no: str | None = None,
        bsr_code: str | None = None,
        cin: str | None = None,
        deposit_date: str | None = None,
    ) -> dict:
        row = tds_challan_repository.get(org_id, challan_id=challan_id) or {}
        if challan_no:
            from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import resolve_tds_filing_connector

            connector = resolve_tds_filing_connector()
            if connector and hasattr(connector, "validate_challan"):
                validation = connector.validate_challan(
                    challan_no=challan_no,
                    bsr_code=bsr_code,
                    amount=float(row.get("amount") or 0),
                )
                if not validation.get("valid"):
                    raise ValueError(validation.get("message") or "Challan validation failed")
        updated = tds_challan_repository.set_status(
            org_id,
            challan_id=challan_id,
            status="paid",
            challan_no=challan_no,
            bsr_code=bsr_code,
            cin=cin,
            deposit_date=deposit_date,
        )
        emit_compliance_alert(org_id, alert_type="tds.challan.paid", summary=f"TDS challan {challan_id} marked paid")
        try:
            from app.modules.erp.compliance.services.obligation_service import obligation_service

            period = str(updated.get("deposit_date") or deposit_date or "")[:7] or None
            obligation_service.complete_by_source(org_id, compliance_code="TDS_CHALLAN", return_period=period, source_id=challan_id)
        except Exception:
            pass
        return updated

    def list_challans(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return tds_challan_repository.list(org_id, status=status)


tds_challan_service = TdsChallanService()
