from __future__ import annotations

from app.modules.erp.accounts_payable.validators.gstin_validator import validate_gstin


def classify_vendor_from_extraction(extracted_data: dict) -> dict:
    vendor_name = str(extracted_data.get("vendor_name") or extracted_data.get("vendor") or "").strip()
    gstin = str(extracted_data.get("gstin") or extracted_data.get("vendor_gstin") or "").strip().upper() or None
    confidence = 0.9 if vendor_name else 0.5
    if gstin:
        try:
            validate_gstin(gstin)
            confidence = min(0.99, confidence + 0.05)
        except ValueError:
            confidence = 0.4
    return {
        "vendor_name": vendor_name,
        "gstin": gstin,
        "vendor_id": extracted_data.get("vendor_id"),
        "confidence": {"vendor_confidence": confidence, "requires_review": confidence < 0.85},
    }
