from __future__ import annotations

from datetime import date, datetime


def detect_payment_anomalies(
    *,
    amount: float,
    beneficiary_ref: str | None,
    history_amounts: list[float],
    recent_duplicate: bool,
    beneficiary_verified: bool,
    scheduled_date: str | None = None,
    new_beneficiary: bool = False,
) -> dict:
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
