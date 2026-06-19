from __future__ import annotations


def classify_narration(narration: str) -> str:
    text = (narration or "").upper()
    if "SALARY" in text or "PAYROLL" in text:
        return "payroll"
    if "NEFT" in text or "RTGS" in text or "IMPS" in text:
        return "bank_transfer"
    if "CHARGE" in text or "FEE" in text:
        return "bank_charge"
    if "GST" in text or "TAX" in text:
        return "tax"
    return "general"
