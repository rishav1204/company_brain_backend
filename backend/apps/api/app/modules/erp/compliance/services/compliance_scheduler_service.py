from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.engine.scheduler_engine import generation_periods
from app.modules.erp.compliance.services.escalation_service import escalation_service
from app.modules.erp.compliance.services.obligation_service import obligation_service
from app.modules.erp.compliance.services.penalty_service import penalty_service
from app.modules.erp.compliance.services.reminder_service import reminder_service


class ComplianceSchedulerService:
    def run_daily(self, org_id: str) -> dict:
        obligation_service.ensure_rules(org_id)
        generated = obligation_service.generate_for_periods(org_id, periods=generation_periods(months_ahead=3))
        refreshed = obligation_service.refresh_statuses(org_id)
        reminders = reminder_service.process_due(org_id)
        escalations = escalation_service.process_overdue(org_id)
        penalties = penalty_service.refresh_overdue_penalties(org_id)
        tds_jobs = self._run_tds_side_effects(org_id)
        return {
            "org_id": org_id,
            "generated": generated.get("generated", 0),
            "status_refreshed": refreshed,
            "reminders_sent": reminders.get("processed", 0),
            "escalations": escalations.get("escalated", 0),
            "penalties_estimated": penalties,
            "tds_jobs": tds_jobs,
        }

    def _run_tds_side_effects(self, org_id: str) -> dict:
        """Preserve tax-module TDS reminders from legacy daily scan."""
        from datetime import date as dt

        today = dt.today()
        result: dict = {}
        try:
            from app.modules.erp.tax.services.tds_service import tds_service
            from app.modules.erp.tax.events.tax_events import emit_compliance_alert

            liability = tds_service.liability_summary(org_id)
            result["liability_total"] = liability.get("total_liability")
            if today.day <= 7 and liability.get("total_liability", 0) > 0:
                emit_compliance_alert(
                    org_id,
                    alert_type="tds.challan.reminder",
                    summary=f"TDS challan due — pending liability ₹{liability['total_liability']:,.2f}",
                    severity="high",
                )
                result["challan_reminder"] = True
        except Exception:
            result["liability_total"] = None
        return result


compliance_scheduler_service = ComplianceSchedulerService()
