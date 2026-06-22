from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def today_iso() -> str:
    return date.today().isoformat()


def parse_date(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def iso(d: date) -> str:
    return d.isoformat()


def add_days(d: date, days: int) -> date:
    return d + timedelta(days=int(days))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

