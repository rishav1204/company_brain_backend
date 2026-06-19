from __future__ import annotations

import base64

from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.tax.engine.form16a_pdf_engine import render_form16a_pdf
from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository
from app.modules.erp.tax.repositories.tds_certificate_repository import tds_certificate_repository


class Form16aService:
    def generate(
        self,
        org_id: str,
        *,
        vendor_id: str,
        quarter: str,
        financial_year: str,
        regenerate: bool = False,
        uploaded_by: str | None = None,
    ) -> dict:
        if not regenerate:
            existing = tds_certificate_repository.get(
                org_id, vendor_id=vendor_id, quarter=quarter, financial_year=financial_year
            )
            if existing and existing.get("document_id"):
                stored = existing.get("payload") if isinstance(existing.get("payload"), dict) else {}
                return {
                    **stored,
                    "certificate_id": existing.get("id"),
                    "document_id": existing.get("document_id"),
                    "pdf_status": "existing",
                }

        vendor = vendor_repository.get(org_id, vendor_id=vendor_id) or {}
        txs = [
            t for t in tds_transaction_repository.list(org_id, limit=1000, vendor_id=vendor_id)
            if str(t.get("quarter") or "") == quarter and str(t.get("financial_year") or "") == financial_year
        ]
        gross_total = round(sum(float(t.get("gross_amount") or 0) for t in txs), 2)
        tds_total = round(sum(float(t.get("tds_amount") or 0) for t in txs), 2)
        payload = {
            "form_type": "16A",
            "vendor_id": vendor_id,
            "vendor_name": vendor.get("vendor_name"),
            "pan": vendor.get("pan"),
            "quarter": quarter,
            "financial_year": financial_year,
            "gross_total": gross_total,
            "tds_total": tds_total,
            "deductions": [
                {
                    "section_code": t.get("section_code"),
                    "gross_amount": t.get("gross_amount"),
                    "tds_amount": t.get("tds_amount"),
                    "deduction_date": t.get("deduction_date"),
                }
                for t in txs
            ],
        }

        pdf_bytes = render_form16a_pdf(payload)
        file_name = f"Form16A_{vendor_id[:8]}_{financial_year}_{quarter}.pdf"
        from app.modules.platform.documents.services.document_service import document_service

        doc = document_service.create_document(
            org_id,
            uploaded_by=uploaded_by,
            document_type="tds_certificate",
            file_name=file_name,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            base64_content=base64.b64encode(pdf_bytes).decode("ascii"),
            metadata={"vendor_id": vendor_id, "quarter": quarter, "financial_year": financial_year},
            enqueue_ocr=False,
        )
        document_id = str(doc.get("id") or doc.get("document", {}).get("id") or "")
        payload["pdf_status"] = "generated"
        payload["document_id"] = document_id
        payload["preview_url"] = doc.get("signed_url") or doc.get("preview_url")
        payload["download_url"] = doc.get("signed_url") or doc.get("download_url")

        cert = tds_certificate_repository.upsert(
            org_id,
            vendor_id=vendor_id,
            quarter=quarter,
            financial_year=financial_year,
            document_id=document_id or None,
            payload=payload,
        )
        payload["certificate_id"] = cert.get("id")
        return payload


form16a_service = Form16aService()
