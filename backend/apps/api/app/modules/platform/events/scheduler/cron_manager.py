"""Cron expressions for scheduled platform jobs (interpreted by scheduler worker)."""

from __future__ import annotations

from datetime import datetime, timezone


DEFAULT_CRON: dict[str, str] = {
    "sla_scan": "*/15 * * * *",
    "escalation_scan": "0 * * * *",
    "reconciliation_daily": "0 6 * * 1-5",
}


def is_due(cron_expression: str, last_run_at: datetime | None, *, min_interval_hours: float = 1.0) -> bool:
    if last_run_at is None:
        return True
    elapsed = (datetime.now(timezone.utc) - last_run_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    return elapsed >= min_interval_hours
