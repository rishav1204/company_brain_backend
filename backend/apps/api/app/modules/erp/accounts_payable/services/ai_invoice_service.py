from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.accounts_payable.ai.duplicate_detector import detect_duplicate_signals
from app.modules.erp.accounts_payable.ai.invoice_reviewer import review_invoice_extraction
from app.modules.erp.accounts_payable.ai.vendor_classifier import classify_vendor_from_extraction
from app.modules.erp.accounts_payable.engine.account_resolver import (
    build_gst_lines_from_extraction,
    resolve_expense_account,
)
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.accounts_payable.services.duplicate_invoice_service import duplicate_invoice_service
from app.modules.erp.accounts_payable.services.invoice_service import invoice_service
from app.modules.erp.accounts_payable.services.vendor_service import vendor_service
from app.modules.platform.documents.ai.ledger_suggester import suggest_ledger_accounts


class AiInvoiceService:
    def create_from_extraction(
        self,
        org_id: str,
        *,
        extracted_data: dict,
        source_document_id: str | None = None,
        created_by: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        vendor_info = classify_vendor_from_extraction(extracted_data)
        vendor_name = str(vendor_info.get("vendor_name") or extracted_data.get("vendor") or "Unknown Vendor")
        gstin = vendor_info.get("gstin") or extracted_data.get("gstin")
        ai_review = review_invoice_extraction(extracted_data, vendor_gstin=gstin)
        ledger_suggestions = suggest_ledger_accounts(extracted_data)

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
        signals = detect_duplicate_signals(dup_check or {})
        if signals.get("block"):
            raise ValueError(f"Duplicate invoice blocked: {signals.get('reason')}")

        expense_account_id = resolve_expense_account(org_id, extracted_data)
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
