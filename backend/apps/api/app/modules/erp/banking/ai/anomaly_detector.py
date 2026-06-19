from __future__ import annotations


def detect_payment_anomalies(*, amount: float, beneficiary_ref: str | None, history_amounts: list[float], beneficiary_verified: bool = True, recent_duplicate: bool = False, scheduled_date: str | None = None, new_beneficiary: bool = False) -> dict:
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
