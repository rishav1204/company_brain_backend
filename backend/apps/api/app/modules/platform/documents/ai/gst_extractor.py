from __future__ import annotations

import re


_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", re.I)
_AMOUNT_RE = re.compile(r"(?:total|grand\s*total|invoice\s*amount|amount\s*payable)[^\d]{0,20}([\d,]+(?:\.\d{1,2})?)", re.I)
_CGST_RE = re.compile(r"cgst[^\d]{0,12}([\d,]+(?:\.\d{1,2})?)", re.I)
_SGST_RE = re.compile(r"sgst[^\d]{0,12}([\d,]+(?:\.\d{1,2})?)", re.I)
_IGST_RE = re.compile(r"igst[^\d]{0,12}([\d,]+(?:\.\d{1,2})?)", re.I)
_CESS_RE = re.compile(r"cess[^\d]{0,12}([\d,]+(?:\.\d{1,2})?)", re.I)


def _parse_amount(match: re.Match[str] | None) -> float:
    if not match:
        return 0.0
    try:
        return float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


class GSTExtractor:
    def extract(self, text: str) -> dict:
        preview = (text or "")[:2000]
        if not preview.strip():
            return {
                "subtotal": 0.0,
                "cgst": 0.0,
                "sgst": 0.0,
                "igst": 0.0,
                "cess": 0.0,
                "total_amount": 0.0,
                "vendor_gstin": None,
                "raw_text_preview": preview,
            }
        cgst = _parse_amount(_CGST_RE.search(preview))
        sgst = _parse_amount(_SGST_RE.search(preview))
        igst = _parse_amount(_IGST_RE.search(preview))
        cess = _parse_amount(_CESS_RE.search(preview))
        total = _parse_amount(_AMOUNT_RE.search(preview))
        tax_sum = cgst + sgst + igst + cess
        subtotal = max(0.0, total - tax_sum) if total > 0 else 0.0
        if total <= 0 and tax_sum > 0:
            total = tax_sum + subtotal
        gstin_match = _GSTIN_RE.search(preview)
        return {
            "subtotal": subtotal,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cess": cess,
            "total_amount": total,
            "vendor_gstin": gstin_match.group(0).upper() if gstin_match else None,
            "raw_text_preview": preview,
        }


gst_extractor = GSTExtractor()
