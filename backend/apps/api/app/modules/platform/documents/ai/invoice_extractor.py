from __future__ import annotations

import re


class InvoiceExtractor:
    def extract(self, text: str) -> dict:
        amount_match = re.search(r"total[:\s]*([0-9]+(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
        invoice_match = re.search(r"invoice(?:\s*no\.?|\s*#)?[:\s]*([A-Za-z0-9\-_/]+)", text, re.IGNORECASE)
        gstin_match = re.search(r"gstin[:\s]*([0-9A-Z]{10,15})", text, re.IGNORECASE)
        total = float(amount_match.group(1)) if amount_match else 0.0
        return {
            "invoice_number": invoice_match.group(1) if invoice_match else "",
            "invoice_date": "",
            "vendor_name": "",
            "gstin": gstin_match.group(1) if gstin_match else "",
            "line_items": [],
            "subtotal": total,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "cess": 0.0,
            "total_amount": total,
            "raw_text_preview": text[:2000],
        }


invoice_extractor = InvoiceExtractor()
