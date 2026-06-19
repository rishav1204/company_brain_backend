from __future__ import annotations

DEFAULT_LEVELS = ["assignee", "manager", "finance_head", "cfo"]


def next_escalation_level(current_level: int, levels: list[str] | None = None) -> tuple[int, str | None]:
    chain = levels or DEFAULT_LEVELS
    if current_level >= len(chain):
        return current_level, None
    idx = min(current_level, len(chain) - 1)
    return idx + 1, chain[idx]


def should_escalate(*, status: str, due_date, today) -> bool:
    from datetime import date

    if status in {"completed", "waived"}:
        return False
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date[:10])
    return due_date < (today or date.today())
