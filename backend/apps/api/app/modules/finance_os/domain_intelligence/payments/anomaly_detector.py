from __future__ import annotations

from datetime import date, datetime


def detect_payment_anomalies(
    *,
    amount: float,
    beneficiary_ref: str | None,
    history_amounts: list[float],
    beneficiary_verified: bool = True,
    recent_duplicate: bool = False,
    scheduled_date: str | None = None,
    new_beneficiary: bool = False,
) -> dict:
    """Banking execution gate — `block_execution` is honoured by payment_execution_service."""
    flags = []
    if amount >= 500_000:
        flags.append({"type": "large_payment", "severity": "high"})
    if new_beneficiary and amount >= 50_000:
        flags.append({"type": "new_beneficiary", "severity": "medium"})
    if not beneficiary_verified and amount >= 100_000:
        flags.append({"type": "unverified_beneficiary", "severity": "critical"})
    if history_amounts:
        avg = sum(history_amounts) / len(history_amounts)
        if avg > 0 and amount > avg * 3:
            flags.append({"type": "abnormal_amount", "severity": "medium"})
    block = any(f.get("severity") == "critical" for f in flags)
    return {"flags": flags, "block_execution": block}


def detect_scheduling_anomalies(
    *,
    amount: float,
    beneficiary_ref: str | None,
    history_amounts: list[float],
    recent_duplicate: bool,
    beneficiary_verified: bool,
    scheduled_date: str | None = None,
    new_beneficiary: bool = False,
) -> dict:
    """Treasury pre-scheduling review — string flags plus approval escalation."""
    flags: list[str] = []
    if recent_duplicate:
        flags.append("duplicate_payment")
    if not beneficiary_verified and beneficiary_ref:
        flags.append("unverified_beneficiary")
    if new_beneficiary and beneficiary_ref:
        flags.append("new_beneficiary")
    if history_amounts:
        avg = sum(history_amounts) / len(history_amounts)
        if avg > 0 and amount > avg * 3:
            flags.append("abnormal_amount")
    if scheduled_date:
        try:
            sd = date.fromisoformat(str(scheduled_date)[:10])
            if sd.weekday() >= 5:
                flags.append("suspicious_timing")
        except ValueError:
            pass
    now = datetime.now()
    if now.hour < 6 or now.hour >= 22:
        flags.append("suspicious_timing")
    block = (
        "duplicate_payment" in flags
        or ("unverified_beneficiary" in flags and amount >= 100_000)
        or ("new_beneficiary" in flags and amount >= 500_000)
    )
    return {"flags": flags, "block_execution": block, "requires_extra_approval": bool(flags)}


def classify_transaction(narration: str) -> str:
    n = narration.lower()
    if "amzn" in n or "aws" in n:
        return "software_expense"
    if "salary" in n or "payroll" in n:
        return "payroll"
    if "neft" in n or "imps" in n or "rtgs" in n:
        return "bank_transfer"
    return "general"


def detect_transaction_anomalies(*, transactions: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    flags = []
    for tx in transactions:
        key = f"{tx.get('amount')}:{tx.get('reference')}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            flags.append({"type": "duplicate_payment", "transaction": tx, "severity": "high"})
    return flags
