from __future__ import annotations

from datetime import date

from app.modules.erp.tax.engine.tds_engine import calculate_tds, financial_year_from_date, quarter_from_date
from app.modules.erp.tax.events.tax_events import emit_tds_calculated
from app.modules.erp.tax.repositories.compliance_repository import tds_section_repository, tds_transaction_repository
from app.modules.erp.tax.repositories.tds_rule_repository import tds_rule_repository
from app.modules.erp.tax.services.tds_posting_service import (
    build_payment_journal_lines,
    build_payment_journal_lines_no_tds,
    resolve_tds_payable_account,
)


class TdsService:
    def _resolve_section(self, org_id: str, *, vendor: dict, payment: dict) -> str:
        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
        payment_meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}

        for source in (payment_meta, vendor_meta):
            if source.get("tds_section"):
                return str(source["tds_section"])

        for source in (payment_meta, vendor_meta):
            ptype = str(source.get("payment_type") or source.get("vendor_type") or "").lower()
            if ptype:
                rule = tds_rule_repository.resolve(org_id, payment_type=ptype, applicable_entity="vendor")
                if rule:
                    return str(rule["section_code"])
            category = str(source.get("expense_category") or "").lower()
            if category:
                rule = tds_rule_repository.resolve(org_id, expense_category=category, applicable_entity="vendor")
                if rule:
                    return str(rule["section_code"])

        return "194C"

    def _section_rates(self, org_id: str, *, section_code: str) -> dict:
        section = tds_section_repository.get_by_code(org_id, section_code=section_code)
        if not section:
            raise ValueError(f"TDS section not found: {section_code}")
        rate_pan = float(section.get("rate_pan") if section.get("rate_pan") is not None else section["rate"])
        rate_no_pan = float(
            section.get("rate_no_pan") if section.get("rate_no_pan") is not None else max(rate_pan * 2, 20)
        )
        threshold = float(section.get("threshold_amount") or 0)
        return {"rate_pan": rate_pan, "rate_no_pan": rate_no_pan, "threshold": threshold}

    def _prior_ytd(self, org_id: str, *, vendor_id: str, section_code: str, financial_year: str) -> float:
        return tds_transaction_repository.sum_ytd(
            org_id, vendor_id=vendor_id, section_code=section_code, financial_year=financial_year
        )

    def calculate(
        self,
        org_id: str,
        *,
        section_code: str,
        gross_amount: float,
        prior_ytd: float = 0,
        pan_present: bool = True,
        vendor_id: str | None = None,
    ) -> dict:
        rates = self._section_rates(org_id, section_code=section_code)
        if vendor_id and prior_ytd == 0:
            fy = financial_year_from_date(str(date.today()))
            prior_ytd = self._prior_ytd(org_id, vendor_id=vendor_id, section_code=section_code, financial_year=fy)
        result = calculate_tds(
            gross_amount=gross_amount,
            rate_pan=rates["rate_pan"],
            rate_no_pan=rates["rate_no_pan"],
            threshold=rates["threshold"],
            prior_ytd=prior_ytd,
            pan_present=pan_present,
        )
        return {**result, "section_code": section_code}

    def preview_for_invoice(
        self,
        org_id: str,
        *,
        vendor_id: str,
        gross_amount: float,
        section_code: str | None = None,
        expense_category: str | None = None,
        payment_type: str | None = None,
    ) -> dict:
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        vendor = vendor_repository.get(org_id, vendor_id=vendor_id) or {}
        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
        section = section_code
        if not section:
            if payment_type:
                rule = tds_rule_repository.resolve(org_id, payment_type=payment_type, applicable_entity="vendor")
                section = rule["section_code"] if rule else None
            if not section and expense_category:
                rule = tds_rule_repository.resolve(org_id, expense_category=expense_category, applicable_entity="vendor")
                section = rule["section_code"] if rule else None
            if not section and vendor_meta.get("tds_section"):
                section = str(vendor_meta["tds_section"])
        if not section:
            section = self._resolve_section(org_id, vendor=vendor, payment={"metadata": {}})
        pan_present = bool(vendor.get("pan"))
        fy = financial_year_from_date(str(date.today()))
        prior_ytd = self._prior_ytd(org_id, vendor_id=vendor_id, section_code=section, financial_year=fy)
        calc = self.calculate(
            org_id,
            section_code=section,
            gross_amount=gross_amount,
            prior_ytd=prior_ytd,
            pan_present=pan_present,
        )
        return {"vendor_id": vendor_id, **calc}

    def deduct(
        self,
        org_id: str,
        *,
        payment_id: str,
        section_code: str | None = None,
        payable_account_id: str | None = None,
        bank_account_id: str | None = None,
        tds_payable_account_id: str | None = None,
    ) -> dict:
        from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        existing = tds_transaction_repository.get_by_source(org_id, source_type="ap_payment", source_id=payment_id)
        payment = payment_repository.get(org_id, payment_id=payment_id)
        if not payment:
            raise ValueError("Payment not found")

        vendor = vendor_repository.get(org_id, vendor_id=str(payment.get("vendor_id") or "")) or {}
        gross = float(payment.get("amount") or 0)
        payment_date = str(payment.get("payment_date") or "")[:10]
        fy = financial_year_from_date(payment_date) if payment_date else financial_year_from_date(str(date.today()))
        quarter = quarter_from_date(payment_date) if payment_date else quarter_from_date(str(date.today()))
        section = section_code or self._resolve_section(org_id, vendor=vendor, payment=payment)
        pan_present = bool(vendor.get("pan"))
        prior_ytd = self._prior_ytd(
            org_id,
            vendor_id=str(payment.get("vendor_id") or ""),
            section_code=section,
            financial_year=fy,
        )
        calc = self.calculate(
            org_id,
            section_code=section,
            gross_amount=gross,
            prior_ytd=prior_ytd,
            pan_present=pan_present,
        )

        from app.modules.erp.tax.services.tax_account_setup_service import tax_account_setup_service

        if calc.get("applicable") or existing:
            tax_account_setup_service.require_tds_payable(org_id)

        meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
        invoice_id = None
        allocations = meta.get("allocations") or []
        if allocations:
            invoice_id = str(allocations[0].get("invoice_id") or "") or None

        row = None
        if existing:
            tds_amount = float(existing.get("tds_amount") or 0)
            net_amount = float(existing.get("net_amount") or gross)
        elif calc.get("applicable"):
            row = tds_transaction_repository.create(
                org_id,
                source_type="ap_payment",
                source_id=payment_id,
                section_code=section,
                gross_amount=gross,
                tds_amount=calc["tds_amount"],
                net_amount=calc["net_amount"],
                return_period=payment_date[:7] if payment_date else None,
                vendor_id=str(payment.get("vendor_id") or "") or None,
                invoice_id=invoice_id,
                payment_id=payment_id,
                financial_year=fy,
                quarter=quarter,
                deduction_date=payment_date or None,
                metadata={"vendor_id": str(payment.get("vendor_id") or ""), "rate": calc.get("rate")},
            )
            emit_tds_calculated(
                org_id,
                tds_transaction_id=str(row["id"]),
                section_code=section,
                tds_amount=calc["tds_amount"],
            )
            tds_amount = calc["tds_amount"]
            net_amount = calc["net_amount"]
        else:
            tds_amount = 0.0
            net_amount = gross

        tds_payable_id = tds_payable_account_id or resolve_tds_payable_account(org_id)
        if tds_amount > 0 and payable_account_id and bank_account_id:
            journal_lines = build_payment_journal_lines(
                payable_account_id=payable_account_id,
                bank_account_id=bank_account_id,
                tds_payable_account_id=tds_payable_id,
                gross_amount=gross,
                tds_amount=tds_amount,
                net_amount=net_amount,
            )
        elif payable_account_id and bank_account_id:
            journal_lines = build_payment_journal_lines_no_tds(
                payable_account_id=payable_account_id,
                bank_account_id=bank_account_id,
                amount=gross,
            )
        else:
            journal_lines = []

        return {
            **calc,
            "section_code": section,
            "tds_transaction_id": existing.get("id") if existing else (row.get("id") if row else None),
            "journal_lines": journal_lines,
            "gross_amount": gross,
            "net_amount": net_amount,
            "tds_amount": tds_amount,
        }

    def calculate_for_payment(self, org_id: str, *, payment_id: str, section_code: str | None = None) -> dict | None:
        """Idempotent post-payment hook — skips if deduct() already recorded."""
        existing = tds_transaction_repository.get_by_source(org_id, source_type="ap_payment", source_id=payment_id)
        if existing:
            return {"tds_transaction_id": existing.get("id"), "already_recorded": True}
        try:
            return self.deduct(org_id, payment_id=payment_id, section_code=section_code)
        except ValueError:
            return None

    def liability_summary(self, org_id: str, *, quarter: str | None = None, financial_year: str | None = None) -> dict:
        txs = tds_transaction_repository.list(org_id, limit=1000)
        pending = [t for t in txs if str(t.get("status")) in {"calculated", "pending_deposit"}]
        if quarter:
            pending = [t for t in pending if str(t.get("quarter") or "") == quarter]
        if financial_year:
            pending = [t for t in pending if str(t.get("financial_year") or "") == financial_year]
        by_section: dict[str, dict] = {}
        for tx in pending:
            sec = str(tx.get("section_code") or "unknown")
            bucket = by_section.setdefault(sec, {"section_code": sec, "tds_total": 0.0, "count": 0})
            bucket["tds_total"] = round(bucket["tds_total"] + float(tx.get("tds_amount") or 0), 2)
            bucket["count"] += 1
        total = round(sum(s["tds_total"] for s in by_section.values()), 2)
        return {"total_liability": total, "sections": list(by_section.values()), "transaction_count": len(pending)}

    def vendor_summary(self, org_id: str, *, vendor_id: str | None = None) -> list[dict]:
        txs = tds_transaction_repository.list(org_id, limit=1000, vendor_id=vendor_id)
        by_vendor: dict[str, dict] = {}
        for tx in txs:
            vid = str(tx.get("vendor_id") or (tx.get("metadata") or {}).get("vendor_id") or "unknown")
            bucket = by_vendor.setdefault(vid, {"vendor_id": vid, "gross_total": 0.0, "tds_total": 0.0, "count": 0})
            bucket["gross_total"] = round(bucket["gross_total"] + float(tx.get("gross_amount") or 0), 2)
            bucket["tds_total"] = round(bucket["tds_total"] + float(tx.get("tds_amount") or 0), 2)
            bucket["count"] += 1
        return list(by_vendor.values())

    def list_transactions(self, org_id: str) -> list[dict]:
        return tds_transaction_repository.list(org_id)

    def list_sections(self, org_id: str) -> list[dict]:
        return tds_section_repository.list(org_id)

    def list_rules(self, org_id: str) -> list[dict]:
        return tds_rule_repository.list(org_id)


tds_service = TdsService()
