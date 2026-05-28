from __future__ import annotations

ALLOWED_DECISIONS = frozenset({"approved", "approve", "rejected", "reject", "delegated", "escalated"})


def validate_decision(decision: str) -> str:
    normalized = (decision or "").strip().lower()
    if normalized not in ALLOWED_DECISIONS:
        raise ValueError(f"Invalid approval decision: {decision}")
    if normalized in {"approve"}:
        return "approved"
    if normalized in {"reject"}:
        return "rejected"
    return normalized
