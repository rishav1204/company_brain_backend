from __future__ import annotations

from datetime import date

from app.modules.erp.tax.engine.tcs_engine import calculate_tcs
from app.modules.erp.tax.repositories.compliance_repository import tds_section_repository
from app.modules.erp.tax.repositories.tcs_transaction_repository import tcs_transaction_repository
from app.modules.erp.tax.services.tds_posting_service import resolve_tcs_payable_account


class TcsService:
    def calculate(
        self,
        org_id: str,
        *,
        gross_amount: float,
        section_code: str = "206C",
        prior_ytd: float = 0,
        pan_present: bool = True,
    ) -> dict:
        section = tds_section_repository.get_by_code(org_id, section_code=section_code)
        if not section:
            raise ValueError(f"TCS section not found: {section_code}")
        rate_pan = float(section.get("rate_pan") if section.get("rate_pan") is not None else section["rate"])
        rate_no_pan = float(
            section.get("rate_no_pan") if section.get("rate_no_pan") is not None else max(rate_pan * 2, 20)
        )
        threshold = float(section.get("threshold_amount") or 0)
        result = calculate_tcs(
            gross_amount=gross_amount,
            rate_pan=rate_pan,
            rate_no_pan=rate_no_pan,
            threshold=threshold,
            prior_ytd=prior_ytd,
            pan_present=pan_present,
        )
        return {**result, "section_code": section_code}

    def collect_for_invoice(
        self,
        org_id: str,
        *,
        invoice_id: str,
        customer_id: str,
        gross_amount: float,
        invoice_date: str,
        pan_present: bool = True,
        section_code: str = "206C",
    ) -> dict | None:
        existing = tcs_transaction_repository.get_by_source(org_id, source_type="ar_invoice", source_id=invoice_id)
        if existing:
            return {**existing, "already_recorded": True}

        fy = financial_year_from_date(invoice_date)
        prior_ytd = tcs_transaction_repository.sum_ytd(
            org_id, customer_id=customer_id, section_code=section_code, financial_year=fy
        )
        calc = self.calculate(
            org_id,
            gross_amount=gross_amount,
            section_code=section_code,
            prior_ytd=prior_ytd,
            pan_present=pan_present,
        )
        if not calc.get("applicable"):
            return calc

        row = tcs_transaction_repository.create(
            org_id,
            source_type="ar_invoice",
            source_id=invoice_id,
            customer_id=customer_id,
            section_code=section_code,
            gross_amount=gross_amount,
            tcs_amount=calc["tcs_amount"],
            total_collected=calc["total_collected"],
            return_period=invoice_date[:7],
            financial_year=fy,
            quarter=quarter_from_date(invoice_date),
        )
        return {**calc, "tcs_transaction_id": row.get("id"), "tcs_payable_account_id": resolve_tcs_payable_account(org_id)}

    def list_transactions(self, org_id: str) -> list[dict]:
        return tcs_transaction_repository.list(org_id)


tcs_service = TcsService()
