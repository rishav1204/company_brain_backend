from __future__ import annotations


def validate_budget_available(*, allocated: float, committed: float, consumed: float, requested: float) -> dict:
    remaining = allocated - committed - consumed
    ok = requested <= remaining
    return {
        "available": round(remaining, 2),
        "requested": round(requested, 2),
        "sufficient": ok,
        "shortfall": round(max(0, requested - remaining), 2) if not ok else 0,
    }
