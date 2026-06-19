from __future__ import annotations


def estimate_penalty(*, obligation: dict) -> dict:
    """Stub penalty registry — returns zero until legal templates are finalized."""
    return {
        "penalty_amount": 0.0,
        "interest_amount": 0.0,
        "formula": "stub",
        "obligation_id": obligation.get("id"),
    }
