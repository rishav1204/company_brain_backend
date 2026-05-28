from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

from app.services.db import get_db_conn, set_rls_org

BUSINESS_DAYS = frozenset({0, 1, 2, 3, 4})
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18
REMINDER_HOURS_BEFORE = 4


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@lru_cache(maxsize=64)
def _holiday_dates(org_id: str) -> frozenset[date]:
    try:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT holiday_date::date AS d
                    FROM workflow.org_holidays
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return frozenset(row["d"] for row in cur.fetchall())
    except Exception:
        return frozenset()


def _is_non_business_day(org_id: str, dt: datetime) -> bool:
    current = _to_utc(dt)
    if current.weekday() not in BUSINESS_DAYS:
        return True
    return current.date() in _holiday_dates(org_id)


def add_business_hours(start: datetime, hours: float, *, org_id: str | None = None) -> datetime:
    if hours <= 0:
        return _to_utc(start)
    current = _to_utc(start)
    remaining_minutes = int(hours * 60)
    while remaining_minutes > 0:
        if org_id and _is_non_business_day(org_id, current):
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
            continue
        if current.weekday() not in BUSINESS_DAYS:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
            continue
        if current.hour < BUSINESS_START_HOUR:
            current = current.replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)
        if current.hour >= BUSINESS_END_HOUR:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
            continue
        end_of_day = current.replace(hour=BUSINESS_END_HOUR, minute=0, second=0, microsecond=0)
        available = int((end_of_day - current).total_seconds() // 60)
        if available <= 0:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
            continue
        use = min(available, remaining_minutes)
        current += timedelta(minutes=use)
        remaining_minutes -= use
    return current


def compute_sla_due_at(*, created_at: datetime, sla_hours: float | None, org_id: str | None = None) -> datetime | None:
    if sla_hours is None:
        return None
    return add_business_hours(created_at, float(sla_hours), org_id=org_id)


def compute_reminder_at(*, due_at: datetime | None, org_id: str | None = None) -> datetime | None:
    if due_at is None:
        return None
    return add_business_hours(due_at, -REMINDER_HOURS_BEFORE, org_id=org_id)


def is_sla_breached(due_at: datetime | None, *, now: datetime | None = None) -> bool:
    if due_at is None:
        return False
    ref = _to_utc(now or datetime.now(timezone.utc))
    return ref > _to_utc(due_at)


def is_reminder_due(reminder_at: datetime | None, *, now: datetime | None = None) -> bool:
    if reminder_at is None:
        return False
    ref = _to_utc(now or datetime.now(timezone.utc))
    return ref >= _to_utc(reminder_at)
