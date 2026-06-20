from __future__ import annotations

from typing import Any


def predict_gst_code(
    *,
    vendor_gstin: str | None,
    taxable_amount: float,
    gst_amount: float,
    state_code: str | None = None,
) -> dict[str, Any]:
    if gst_amount <= 0:
        return {"suggested_gst_code": "EXEMPT", "confidence_score": 0.7, "reason": "no_gst"}

    rate = 0.0
    if taxable_amount > 0:
        rate = round((gst_amount / taxable_amount) * 100)

    if rate in (5, 12, 18, 28):
        code = f"GST{rate}"
        confidence = 0.85
    elif rate > 0:
        code = f"GST{rate}"
        confidence = 0.6
    else:
        code = "GST18"
        confidence = 0.4

    if vendor_gstin and state_code and vendor_gstin[:2] == state_code:
        code = code.replace("GST", "CGST+SGST") if "GST" in code else code
    elif vendor_gstin:
        code = f"IGST{rate}" if rate else "IGST18"

    return {
        "suggested_gst_code": code,
        "confidence_score": confidence,
        "inferred_rate": rate,
    }
