from __future__ import annotations

SCHEDULED_JOBS: dict[str, str] = {
    "sla_scan": "scheduler.sla.scan",
    "escalation_scan": "scheduler.escalation.scan",
    "reconciliation_daily": "scheduler.reconciliation.daily",
    "compliance_daily": "scheduler.compliance.daily",
    "treasury_daily": "scheduler.treasury.daily",
    "reports_daily": "scheduler.reports.daily",
    "analytics_daily": "scheduler.analytics.daily",
    "scheduler_tick": "scheduler.tick",
}
