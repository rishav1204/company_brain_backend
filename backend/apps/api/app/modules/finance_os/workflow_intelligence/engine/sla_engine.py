from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def predict_completion(
    *,
    remaining_stage_p95: list[float],
    pending_approvals: int,
    avg_approval_wait_seconds: float,
) -> float:
    base = sum(remaining_stage_p95)
    queue_penalty = pending_approvals * avg_approval_wait_seconds
    return base + queue_penalty


def breach_risk(
    *,
    predicted_completion_seconds: float,
    due_at: datetime | None,
    buffer_seconds: float = 3600,
) -> tuple[str, float]:
    if not due_at:
        return "low", 0.4
    now = datetime.utcnow()
    if due_at.tzinfo:
        now = datetime.now(due_at.tzinfo)
    remaining = (due_at - now).total_seconds()
    if predicted_completion_seconds > remaining:
        return "high", 0.9
    if predicted_completion_seconds > remaining - buffer_seconds:
        return "medium", 0.65
    return "low", 0.3


def format_eta(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(1, int(seconds / 60))} minutes"
    if seconds < 86400:
        return f"{int(seconds / 3600)} hours"
    return f"{int(seconds / 86400)} days"
