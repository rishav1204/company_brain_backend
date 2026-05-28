from __future__ import annotations

SCHEDULED_JOBS: dict[str, str] = {
    "sla_scan": "scheduler.sla.scan",
    "escalation_scan": "scheduler.escalation.scan",
    "reconciliation_daily": "scheduler.reconciliation.daily",
    "scheduler_tick": "scheduler.tick",
}
