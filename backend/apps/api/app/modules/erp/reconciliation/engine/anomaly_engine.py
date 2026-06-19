from __future__ import annotations


def detect_reconciliation_anomalies(
    *,
    bank_tx: dict,
    candidates: list[dict] | None = None,
    history_amounts: list[float] | None = None,
) -> list[dict]:
    flags: list[dict] = []
    amount = float(bank_tx.get("amount") or 0)
    ref = str(bank_tx.get("transaction_reference") or "")
    desc = str(bank_tx.get("description") or "").lower()

    if amount >= 500_000:
        flags.append({"type": "large_transfer", "severity": "medium", "message": "Large bank transfer"})

    if not ref and not bank_tx.get("source_id"):
        flags.append({"type": "reference_missing", "severity": "low", "message": "No reference on bank transaction"})

    if "unknown" in desc or not bank_tx.get("counterparty_ref"):
        flags.append({"type": "unknown_beneficiary", "severity": "medium", "message": "Unknown counterparty"})

    if candidates:
        dup = [c for c in candidates if abs(float(c.get("amount") or 0) - amount) < 0.05 and str(c.get("reference") or "") == ref and ref]
        if len(dup) > 1:
            flags.append({"type": "duplicate_entry", "severity": "high", "message": "Possible duplicate payment/receipt"})

    hist = history_amounts or []
    if hist and amount > 0:
        avg = sum(hist) / len(hist)
        if avg > 0 and amount > avg * 3:
            flags.append({"type": "abnormal_amount", "severity": "medium", "message": "Amount exceeds 3x recent average"})

    return flags
