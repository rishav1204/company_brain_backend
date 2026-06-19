from __future__ import annotations

from calendar import monthrange
from datetime import date


def _add_months(base: date, months: int) -> date:
    month = base.month - 1 + months
    year = base.year + month // 12
    month = month % 12 + 1
    day = min(base.day, monthrange(year, month)[1])
    return date(year, month, day)


def compute_due_date(
    *,
    return_period: str,
    frequency: str,
    due_day: int,
    month_offset: int = 1,
) -> date:
    """Rule-driven due date — no hardcoded obligation types."""
    year, month = int(return_period[:4]), int(return_period[5:7])
    period_end = date(year, month, monthrange(year, month)[1])

    freq = (frequency or "monthly").lower()
    if freq == "monthly":
        base = _add_months(period_end.replace(day=1), month_offset)
    elif freq == "quarterly":
        base = _add_months(period_end.replace(day=1), month_offset)
    elif freq == "annual":
        base = _add_months(period_end.replace(day=1), month_offset)
    else:
        base = _add_months(period_end.replace(day=1), month_offset)

    last_day = monthrange(base.year, base.month)[1]
    return date(base.year, base.month, min(max(due_day, 1), last_day))


def periods_for_generation(*, year: int, month: int, months_ahead: int = 3) -> list[str]:
    periods: list[str] = []
    y, m = year, month
    for _ in range(months_ahead):
        periods.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods
