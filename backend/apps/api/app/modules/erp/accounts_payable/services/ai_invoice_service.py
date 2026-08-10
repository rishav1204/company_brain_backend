from __future__ import annotations

from datetime import date

from app.modules.erp.accounts_payable.engine.account_resolver import (
    build_gst_lines_from_extraction,
    resolve_expense_account,
)
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.accounts_payable.services.duplicate_invoice_service import duplicate_invoice_service
from app.modules.erp.accounts_payable.services.invoice_service import invoice_service
from app.modules.erp.accounts_payable.services.vendor_service import vendor_service
from app.modules.erp.ports.intelligence_registry import intelligence_registry

_AUTO_DRAFT_BANDS = {"auto_suggest", "review_suggested"}


class AiInvoiceService:
    def create_from_document(
        self,
        org_id: str,
        *,
        document_id: str,
        created_by: str | None = None,
        company_id: str | None = None,
        invoice_type: str = "purchase",
    ) -> dict:
        pipeline_result = intelligence_registry.invoice().run_pipeline(
            org_id, document_id=document_id, invoice_type=invoice_type
        )
        return self.create_from_m25(
            org_id,
            extraction_id=pipeline_result["extraction_id"],
            source_document_id=document_id,
            created_by=created_by,
            company_id=company_id,
            pipeline_result=pipeline_result,
        )

    def create_from_m25(
        self,
        org_id: str,
        *,
        extraction_id: str,
        source_document_id: str | None = None,
        created_by: str | None = None,
        company_id: str | None = None,
        pipeline_result: dict | None = None,
    ) -> dict:
        intel = intelligence_registry.invoice()
        extraction = intel.get_extraction(org_id, extraction_id)
        if not extraction:
            raise ValueError("M25 extraction not found")

        dup = intel.latest_duplicate(org_id, extraction_id) or {}
        anomalies = intel.list_anomalies(org_id, extraction_id)
        predictions = intel.list_suggestions(org_id, extraction_id=extraction_id)

        if pipeline_result:
            band = str(pipeline_result.get("confidence_band") or extraction.get("confidence_band") or "manual_review")
            auto_eligible = bool(pipeline_result.get("auto_draft_eligible"))
        else:
            conf = intel.evaluate_confidence(
                extraction=extraction,
                predictions=predictions,
                duplicate_status=str(dup.get("status") or "clean"),
                anomaly_count=len(anomalies),
            )
            band = conf["confidence_band"]
            auto_eligible = conf["auto_draft_eligible"]

        if str(dup.get("status")) == "confirmed":
            raise ValueError("Duplicate invoice blocked: confirmed duplicate")
        if any(str(a.get("severity")) == "high" for a in anomalies):
            raise ValueError("High severity anomaly blocks auto AP draft")
        if band not in _AUTO_DRAFT_BANDS and not auto_eligible:
            raise ValueError(f"Confidence band {band} requires manual review before AP draft")

        extracted_data = self._m25_to_extracted(extraction, predictions)
        return self.create_from_extraction(
            org_id,
            extracted_data=extracted_data,
            source_document_id=source_document_id or extraction.get("document_id"),
            created_by=created_by,
            company_id=company_id,
        )

    def _m25_to_extracted(self, extraction: dict, predictions: list[dict]) -> dict:
        ledger_pred = next((p for p in predictions if p.get("prediction_type") == "ledger"), None)
        gst_pred = next((p for p in predictions if p.get("prediction_type") == "gst"), None)
        meta = extraction.get("metadata") if isinstance(extraction.get("metadata"), dict) else {}
        return {
            "invoice_number": extraction.get("invoice_number"),
            "invoice": extraction.get("invoice_number"),
            "invoice_date": extraction.get("invoice_date"),
            "date": extraction.get("invoice_date"),
            "due_date": extraction.get("due_date"),
            "vendor_name": extraction.get("vendor_name"),
            "vendor": extraction.get("vendor_name"),
            "gstin": extraction.get("vendor_gstin"),
            "subtotal": extraction.get("taxable_amount"),
            "amount": extraction.get("taxable_amount"),
            "gst_amount": extraction.get("gst_amount"),
            "total_amount": extraction.get("total_amount"),
            "total": extraction.get("total_amount"),
            "line_items": meta.get("line_items") or [],
            "expense_account_id": (ledger_pred or {}).get("suggested_account_id"),
            "suggested_gst_code": (gst_pred or {}).get("suggested_gst_code"),
            "m25_extraction_id": extraction.get("id"),
        }

    def create_from_extraction(
        self,
        org_id: str,
        *,
        extracted_data: dict,
        source_document_id: str | None = None,
        created_by: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        ap_intel = intelligence_registry.ap_risk()
        vendor_info = ap_intel.classify_vendor_from_extraction(extracted_data)
        vendor_name = str(vendor_info.get("vendor_name") or extracted_data.get("vendor") or "Unknown Vendor")
        gstin = vendor_info.get("gstin") or extracted_data.get("gstin")
        ai_review = ap_intel.review_invoice_extraction(extracted_data, vendor_gstin=gstin)
        ledger_suggestions = ap_intel.suggest_ledger_accounts(extracted_data, org_id=org_id)

        vendor_id = vendor_info.get("vendor_id")
        vendor_row: dict | None = None
        if vendor_id:
            vendor_row = vendor_repository.get(org_id, vendor_id=str(vendor_id))
        if not vendor_id:
            vendor = vendor_service.create_vendor(
                org_id,
                vendor_name=vendor_name,
                gstin=gstin,
                company_id=company_id,
                created_by=created_by or "ai.ap",
            )
            vendor_id = str(vendor["id"])
            vendor_row = vendor
        elif vendor_row:
            vendor_id = str(vendor_row["id"])

        invoice_number = str(extracted_data.get("invoice") or extracted_data.get("invoice_number") or "INV-UNKNOWN")
        invoice_date = str(extracted_data.get("invoice_date") or extracted_data.get("date") or date.today().isoformat())[:10]
        subtotal = float(extracted_data.get("subtotal") or extracted_data.get("amount") or 0)
        gst = float(
            (extracted_data.get("cgst") or 0)
            + (extracted_data.get("sgst") or 0)
            + (extracted_data.get("igst") or 0)
            or extracted_data.get("gst_amount")
            or 0
        )
        total = float(extracted_data.get("total_amount") or extracted_data.get("total") or (subtotal + gst))

        dup_check = duplicate_invoice_service.check_duplicate(
            org_id,
            vendor_id=str(vendor_id),
            invoice_number=invoice_number,
            total_amount=total,
            invoice_date=invoice_date,
        )
        signals = ap_intel.duplicate_signals(dup_check or {})
        if signals.get("block"):
            raise ValueError(f"Duplicate invoice blocked: {signals.get('reason')}")

        expense_account_id = extracted_data.get("expense_account_id") or resolve_expense_account(org_id, extracted_data)
        gst_line_defs = build_gst_lines_from_extraction(org_id, extracted_data, company_id=company_id)
        invoice_lines: list[dict] = []
        if expense_account_id and subtotal > 0:
            invoice_lines.append({
                "account_id": expense_account_id,
                "line_type": "expense",
                "amount": subtotal,
                "description": "Expense (AI suggested)",
                "cost_center_id": extracted_data.get("cost_center_id"),
            })
        for gl in gst_line_defs:
            invoice_lines.append({
                "account_id": gl["account_id"],
                "line_type": "gst",
                "amount": gl["amount"],
                "description": gl.get("description"),
                "tax_code": gl.get("tax_code"),
            })

        vendor_meta = (vendor_row or {}).get("metadata") if isinstance((vendor_row or {}).get("metadata"), dict) else {}
        discount_rate = float(vendor_meta.get("early_payment_discount_rate") or 0)
        discount_days = int(vendor_meta.get("early_payment_discount_days") or 0)
        invoice_metadata = {
            "expense_account_id": expense_account_id,
            "ledger_suggestions": ledger_suggestions,
            "ai_review": ai_review,
            "early_payment_discount_rate": discount_rate,
            "early_payment_discount_days": discount_days,
            "cost_center_id": extracted_data.get("cost_center_id"),
            "m25_extraction_id": extracted_data.get("m25_extraction_id"),
        }

        result = invoice_service.create_invoice(
            org_id,
            vendor_id=str(vendor_id),
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_amount=subtotal,
            gst_amount=gst,
            total_amount=total,
            source_document_id=source_document_id,
            company_id=company_id,
            created_by=created_by or "ai.ap",
            expense_account_id=expense_account_id,
            lines=invoice_lines or None,
            metadata=invoice_metadata,
        )
        invoice_service.submit_for_review(org_id, invoice_id=str(result["invoice"]["id"]), actor_id=created_by)
        return {
            **result,
            "ai_signals": signals,
            "vendor_classification": vendor_info,
            "ai_review": ai_review,
            "ledger_suggestions": ledger_suggestions,
        }


ai_invoice_service = AiInvoiceService()
