from __future__ import annotations


def detect_duplicate_signals(dup_check: dict) -> dict:
    if dup_check.get("duplicate"):
        return {
            "block": True,
            "reason": "vendor+invoice_number+amount+date match",
            "existing_invoice_id": (dup_check.get("existing_invoice") or {}).get("id"),
        }
    return {"block": False, "reason": None}
