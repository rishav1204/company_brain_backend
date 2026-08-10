from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def classify_vendor_from_extraction(extracted_data: dict) -> dict:
    vendor_name = str(extracted_data.get("vendor_name") or extracted_data.get("vendor") or "").strip()
    gstin = str(extracted_data.get("gstin") or extracted_data.get("vendor_gstin") or "").strip().upper() or None
    confidence = 0.9 if vendor_name else 0.5
    if gstin:
        if domain_calc.gstin_error(gstin) is None:
            confidence = min(0.99, confidence + 0.05)
        else:
            confidence = 0.4
    return {
        "vendor_name": vendor_name,
        "gstin": gstin,
        "vendor_id": extracted_data.get("vendor_id"),
        "confidence": {"vendor_confidence": confidence, "requires_review": confidence < 0.85},
    }
