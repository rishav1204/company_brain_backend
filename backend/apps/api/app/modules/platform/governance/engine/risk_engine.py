from __future__ import annotations


def assess_risk(*, action: str, attrs: dict) -> str:
    amount = float(attrs.get("amount", 0) or 0)
    vendor_risk = str(attrs.get("vendor_risk") or "").lower()
    if attrs.get("fiscal_period_open") is False:
        return "CRITICAL"
    if vendor_risk in {"critical", "blacklisted"}:
        return "CRITICAL"
    if vendor_risk == "high" or amount >= 2_500_000:
        return "HIGH"
    if amount >= 500_000 or attrs.get("compliance_risk"):
        return "MEDIUM"
    if amount >= 50_000:
        return "LOW"
    return "LOW"


def risk_blocks_execution(risk_level: str, *, human_approved: bool) -> bool:
    if risk_level == "CRITICAL":
        return True
    if risk_level == "HIGH" and not human_approved:
        return False
    return False
