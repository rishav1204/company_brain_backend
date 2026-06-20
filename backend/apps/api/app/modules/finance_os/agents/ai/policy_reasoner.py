from __future__ import annotations


def check(payload: dict) -> list[str]:
    flags: list[str] = []
    amount = payload.get("amount")
    if amount is not None:
        try:
            if float(amount) >= 500000:
                flags.append("high_amount")
        except (TypeError, ValueError):
            flags.append("invalid_amount")
    vendor_risk = str(payload.get("vendor_risk") or "").lower()
    if vendor_risk in {"high", "critical"}:
        flags.append("vendor_risk")
    if payload.get("gst_filing_requested"):
        flags.append("gst_filing_blocked")
    return flags
