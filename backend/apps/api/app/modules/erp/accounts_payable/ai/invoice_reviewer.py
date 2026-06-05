from __future__ import annotations

from app.modules.erp.accounts_payable.validators.gstin_validator import validate_gstin


def review_invoice_extraction(extracted_data: dict, *, vendor_gstin: str | None = None) -> dict:
    """AI invoice review: unusual vendors, suspicious GST, amount anomalies."""
    flags: list[dict] = []
    vendor_name = str(extracted_data.get("vendor_name") or extracted_data.get("vendor") or "").strip()
    gstin = str(extracted_data.get("gstin") or extracted_data.get("vendor_gstin") or vendor_gstin or "").strip().upper()

    if not vendor_name or len(vendor_name) < 3:
        flags.append({"type": "unusual_vendor", "severity": "medium", "detail": "Vendor name missing or too short"})

    if gstin:
        try:
            validate_gstin(gstin)
        except ValueError as exc:
            flags.append({"type": "suspicious_gst", "severity": "high", "detail": str(exc)})
    else:
        gst_amount = float(
            (extracted_data.get("cgst") or 0)
            + (extracted_data.get("sgst") or 0)
            + (extracted_data.get("igst") or 0)
            or extracted_data.get("gst_amount")
            or 0
        )
        if gst_amount > 0:
            flags.append({
                "type": "suspicious_gst",
                "severity": "high",
                "detail": "GST charged but vendor GSTIN missing",
            })

    subtotal = float(extracted_data.get("subtotal") or extracted_data.get("amount") or 0)
    total = float(extracted_data.get("total_amount") or extracted_data.get("total") or 0)
    if subtotal > 0 and total > 0 and total < subtotal:
        flags.append({"type": "amount_anomaly", "severity": "high", "detail": "Total less than subtotal"})

    requires_review = any(f["severity"] in {"high", "medium"} for f in flags)
    return {"flags": flags, "requires_review": requires_review, "flag_count": len(flags)}
