from __future__ import annotations

from typing import Any

OVERLOAD_THRESHOLD = 50
PASS_THROUGH_THRESHOLD = 0.98


def recommend_stage_removal(
    *,
    step_key: str,
    pass_through_rate: float,
    rejection_rate: float,
    avg_hours: float,
) -> dict[str, Any] | None:
    if pass_through_rate >= PASS_THROUGH_THRESHOLD and rejection_rate <= 0.01:
        return {
            "recommendation_type": "remove_stage",
            "recommendation": f"Remove or merge stage '{step_key}' — {pass_through_rate:.0%} pass-through with no rejections",
            "impact_score": round(avg_hours, 2),
            "metadata": {"step_key": step_key, "pass_through_rate": pass_through_rate},
        }
    return None


def recommend_delegation(*, assignee_id: str, pending_count: int, avg_wait_hours: float) -> dict[str, Any] | None:
    if pending_count >= OVERLOAD_THRESHOLD:
        return {
            "recommendation_type": "delegate",
            "recommendation": f"Approver {assignee_id} has {pending_count} pending approvals — consider delegation or load balancing",
            "impact_score": round(pending_count * avg_wait_hours / 10, 2),
            "metadata": {"assignee_id": assignee_id, "pending_count": pending_count},
        }
    return None


def detect_queue_overload(pending_by_assignee: dict[str, int], threshold: int = OVERLOAD_THRESHOLD) -> list[dict[str, Any]]:
    return [
        {"assignee_id": uid, "pending_count": cnt, "overloaded": cnt >= threshold}
        for uid, cnt in pending_by_assignee.items()
        if cnt >= threshold
    ]


def pass_through_rate(approved: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return approved / total
