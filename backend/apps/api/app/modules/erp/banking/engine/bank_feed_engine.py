from __future__ import annotations

from typing import Any


def normalize_transaction(row: dict[str, Any]) -> dict[str, Any]:
    """Canonical format before DB insert."""
    amount = float(row.get("amount") or 0)
    tx_type = str(row.get("type") or "").lower()
    if tx_type not in {"debit", "credit"}:
        tx_type = "credit" if amount >= 0 else "debit"
    return {
        "date": str(row.get("date") or row.get("transaction_date") or row.get("occurred_at") or "")[:10],
        "amount": abs(amount),
        "type": tx_type,
        "reference": str(row.get("reference") or row.get("transaction_reference") or row.get("id") or "")[:128],
        "narration": str(row.get("narration") or row.get("description") or "")[:512],
    }


def normalize_batch(rows: list[dict]) -> list[dict]:
    return [normalize_transaction(r) for r in rows if r]
