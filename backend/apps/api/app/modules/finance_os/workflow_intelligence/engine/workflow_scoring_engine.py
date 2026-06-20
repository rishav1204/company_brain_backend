from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def efficiency_score(*, actual_seconds: float, sla_target_seconds: float | None, historical_p50: float | None = None) -> float:
    target = sla_target_seconds or historical_p50 or actual_seconds or 1
    if target <= 0:
        return 50.0
    raw = 100.0 * (1.0 - actual_seconds / target)
    return round(max(0.0, min(100.0, raw)), 2)


def efficiency_band(score: float) -> str:
    if score > 90:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "needs_review"
    return "poor"


def org_health_score(*, efficiency_scores: list[float], breach_risk_count: int, overload_count: int) -> float:
    if not efficiency_scores:
        return 50.0
    avg_eff = sum(efficiency_scores) / len(efficiency_scores)
    penalty = breach_risk_count * 5 + overload_count * 3
    return round(max(0.0, min(100.0, avg_eff - penalty)), 2)


def health_band(score: float) -> str:
    return efficiency_band(score)
