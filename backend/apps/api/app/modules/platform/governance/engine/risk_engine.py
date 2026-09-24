from __future__ import annotations

_READ_ACTION_TOKENS = frozenset({"read", "list", "get", "status", "summary", "stream", "sse", "watch", "export"})


def requires_open_fiscal_period(action: str) -> bool:
    """Fiscal period lock is for posting/mutations, not inbox or read APIs."""
    a = (action or "").strip().lower()
    if not a:
        return False
    if a in _READ_ACTION_TOKENS:
        return False
    leaf = a.rsplit(".", 1)[-1]
    if leaf in _READ_ACTION_TOKENS:
        return False
    if any(tok in a for tok in ("stream", "sse", "status", "summary")):
        return False
    return True


def assess_risk(*, action: str, attrs: dict) -> str:
    amount = float(attrs.get("amount", 0) or 0)
    vendor_risk = str(attrs.get("vendor_risk") or "").lower()
    if attrs.get("fiscal_period_open") is False and requires_open_fiscal_period(action):
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
        return True
    return False
