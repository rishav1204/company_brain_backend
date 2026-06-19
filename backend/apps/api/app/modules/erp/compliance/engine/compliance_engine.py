from __future__ import annotations

from datetime import date, timedelta


def refresh_status(*, due_date: date, status: str, today: date | None = None) -> str:
    if status in {"completed", "waived"}:
        return status
    today = today or date.today()
    if due_date < today:
        return "overdue"
    if due_date <= today + timedelta(days=7):
        return "due_soon"
    return "upcoming"


def priority_for_status(status: str) -> str:
    if status == "overdue":
        return "critical"
    if status == "due_soon":
        return "high"
    return "medium"


def calendar_color(status: str) -> str:
    mapping = {
        "completed": "green",
        "waived": "green",
        "upcoming": "yellow",
        "due_soon": "orange",
        "overdue": "red",
    }
    return mapping.get(status, "yellow")
