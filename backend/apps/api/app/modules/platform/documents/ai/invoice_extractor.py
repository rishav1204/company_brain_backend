from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.invoice_extractor import extract_regex
from app.modules.finance_os.invoice_ai.ai.llm_invoice_extractor import InvoiceExtractor as M25InvoiceExtractor

_m25_extractor = M25InvoiceExtractor()


class InvoiceExtractor:
    """Platform stub — delegates to M25 invoice extractor."""

    def extract(self, text: str, org_id: str | None = None) -> dict:
        if org_id:
            result = _m25_extractor.extract(org_id, text)
        else:
            result = extract_regex(text)
        return {
            "invoice_number": result.get("invoice_number") or "",
            "invoice_date": result.get("invoice_date") or "",
            "vendor_name": result.get("vendor_name") or "",
            "gstin": result.get("vendor_gstin") or result.get("gstin") or "",
            "line_items": result.get("line_items") or [],
            "subtotal": float(result.get("taxable_amount") or result.get("subtotal") or 0),
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": float(result.get("gst_amount") or 0),
            "cess": 0.0,
            "total_amount": float(result.get("total_amount") or 0),
            "raw_text_preview": text[:2000],
            "extraction_confidence": result.get("extraction_confidence"),
        }


invoice_extractor = InvoiceExtractor()
