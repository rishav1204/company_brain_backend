from __future__ import annotations

from app.core.config import settings
from app.modules.platform.events.services.event_service import platform_event_service


class SchedulingService:
    """Emit scheduler events — workers execute heavy work."""

    def emit_scheduler_tick(self, org_id: str, *, job: str, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.tick",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": job},
            trace_id=trace_id,
        )

    def emit_sla_scan(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.sla.scan",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "sla_scan"},
            trace_id=trace_id,
        )

    def emit_escalation_scan(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.escalation.scan",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "escalation_scan"},
            trace_id=trace_id,
        )

    def emit_reconciliation_job(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.reconciliation.daily",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "daily_reconciliation"},
            trace_id=trace_id,
        )

    def emit_compliance_job(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.compliance.daily",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "compliance_daily"},
            trace_id=trace_id,
        )

    def emit_notification_digest(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.notifications.digest",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "notification_digest"},
            trace_id=trace_id,
        )

    def emit_reports_daily(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.reports.daily",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "reports_daily"},
            trace_id=trace_id,
        )

    def emit_analytics_daily(self, org_id: str, *, trace_id: str | None = None) -> dict:
        return platform_event_service.publish(
            event_type="scheduler.analytics.daily",
            org_id=org_id,
            source="platform.scheduler",
            payload={"job": "analytics_daily"},
            trace_id=trace_id,
        )

    def run_org_scheduled_emissions(self, org_id: str) -> dict:
        allowed = [o.strip() for o in settings.scheduler_org_ids.split(",") if o.strip()]
        if allowed and org_id not in allowed:
            return {"org_id": org_id, "emitted": [], "skipped": True, "reason": "org_not_scheduled"}
        emitted = {
            "sla": self.emit_sla_scan(org_id),
            "escalation": self.emit_escalation_scan(org_id),
            "reconciliation": self.emit_reconciliation_job(org_id),
            "compliance": self.emit_compliance_job(org_id),
            "notification_digest": self.emit_notification_digest(org_id),
        }
        return {"org_id": org_id, "emitted": list(emitted.keys())}


scheduling_service = SchedulingService()
