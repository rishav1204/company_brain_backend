from __future__ import annotations

import re
from typing import Any


_INVOICE_NO = re.compile(
    r"(?:invoice\s*(?:no|number|#)\.?[:\s]*)([A-Z0-9\-/]+)",
    re.I,
)
_GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b")
_TOTAL = re.compile(r"(?:total|grand\s*total|amount\s*payable)[:\s]*(?:rs\.?|inr)?\s*([\d,]+\.?\d*)", re.I)
_VENDOR = re.compile(r"(?:from|vendor|supplier|billed\s*by)[:\s]*([A-Za-z0-9 &.,'-]{3,80})", re.I)
_DATE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
_GST = re.compile(r"(?:cgst|sgst|igst|gst)[:\s]*(?:rs\.?|inr)?\s*([\d,]+\.?\d*)", re.I)


def _parse_amount(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return 0.0


def extract_regex(text: str) -> dict[str, Any]:
    invoice_match = _INVOICE_NO.search(text)
    gstin_match = _GSTIN.search(text)
    total_match = _TOTAL.search(text)
    vendor_match = _VENDOR.search(text)
    date_match = _DATE.search(text)
    gst_matches = _GST.findall(text)
    gst_total = sum(_parse_amount(g) for g in gst_matches)

    fields_found = sum(
        1 for v in [invoice_match, gstin_match, total_match, vendor_match, date_match] if v
    )
    confidence = min(0.95, 0.35 + fields_found * 0.12)

    return {
        "invoice_number": invoice_match.group(1) if invoice_match else None,
        "vendor_name": vendor_match.group(1).strip() if vendor_match else None,
        "vendor_gstin": gstin_match.group(0) if gstin_match else None,
        "invoice_date": date_match.group(1) if date_match else None,
        "total_amount": _parse_amount(total_match.group(1) if total_match else None),
        "gst_amount": gst_total,
        "taxable_amount": max(
            0,
            _parse_amount(total_match.group(1) if total_match else None) - gst_total,
        ),
        "extraction_confidence": confidence,
        "method": "regex",
    }
