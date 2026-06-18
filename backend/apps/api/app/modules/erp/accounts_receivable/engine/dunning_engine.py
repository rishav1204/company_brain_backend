from __future__ import annotations

DUNNING_STAGES = (
    {"key": "pre_due_reminder", "days_before_due": 7, "priority": "low"},
    {"key": "due_date_reminder", "days_before_due": 0, "priority": "medium"},
    {"key": "overdue_15", "days_overdue": 15, "priority": "medium"},
    {"key": "overdue_30", "days_overdue": 30, "priority": "high"},
    {"key": "overdue_90", "days_overdue": 90, "priority": "critical"},
)


def determine_dunning_action(*, aging_days: int) -> dict | None:
    if aging_days <= -7:
        return {"stage": "pre_due_reminder", "action": "send_reminder", "priority": "low"}
    if -7 < aging_days <= 0:
        return {"stage": "due_date_reminder", "action": "send_reminder", "priority": "medium"}
    if 0 < aging_days <= 15:
        return {"stage": "overdue_15", "action": "escalation", "priority": "medium"}
    if 15 < aging_days <= 30:
        return {"stage": "overdue_30", "action": "collection_workflow", "priority": "high"}
    if 30 < aging_days <= 90:
        return {"stage": "overdue_30", "action": "collection_workflow", "priority": "high"}
    if aging_days > 90:
        return {"stage": "overdue_90", "action": "legal_review_workflow", "priority": "critical"}
    return None
