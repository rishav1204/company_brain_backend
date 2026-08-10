from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.services.escalation_service import escalation_service
from app.modules.erp.compliance.services.obligation_service import obligation_service
from app.modules.erp.compliance.services.penalty_service import penalty_service
from app.modules.erp.ports.intelligence_registry import intelligence_registry


class ComplianceDashboardService:
    def build(self, org_id: str) -> dict:
        today = date.today()
        all_items = obligation_service.list(org_id)
        today_items = [i for i in all_items if str(i.get("due_date"))[:10] == today.isoformat() and i.get("status") not in {"completed", "waived"}]
        upcoming_7d = obligation_service.upcoming(org_id, within_days=7)
        overdue = obligation_service.list(org_id, status="overdue")
        escalations = escalation_service.list_open(org_id)
        exposure = penalty_service.total_exposure(org_id)
        by_regulator: dict[str, int] = {}
        for item in all_items:
            if item.get("status") in {"completed", "waived"}:
                continue
            reg = str(item.get("regulator") or "Other")
            by_regulator[reg] = by_regulator.get(reg, 0) + 1
        return {
            "today": today_items,
            "upcoming_7d": upcoming_7d,
            "overdue": overdue,
            "escalations_open": escalations,
            "penalty_exposure_total": exposure,
            "risk_score": intelligence_registry.compliance().compute_risk_score(
                overdue=overdue,
                escalations=escalations,
                exposure=exposure,
            ),
            "by_regulator": by_regulator,
        }


compliance_dashboard_service = ComplianceDashboardService()
