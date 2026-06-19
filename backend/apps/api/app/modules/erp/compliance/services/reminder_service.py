from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.events.compliance_events import emit_compliance_due
from app.modules.erp.compliance.repositories.compliance_repository import compliance_reminder_repository


class ReminderService:
    def schedule_for_obligation(self, org_id: str, *, obligation_id: str, rule: dict, due_date: date) -> int:
        offsets = rule.get("reminder_offsets_days") or [30, 15, 7, 3, 1]
        if isinstance(offsets, str):
            import json

            offsets = json.loads(offsets)
        count = 0
        for offset in offsets:
            try:
                days = int(offset)
            except (TypeError, ValueError):
                continue
            reminder_date = (due_date - timedelta(days=days)).isoformat()
            compliance_reminder_repository.create(org_id, obligation_id=obligation_id, reminder_date=reminder_date)
            count += 1
        return count

    def process_due(self, org_id: str, *, today: date | None = None) -> dict:
        today = today or date.today()
        due_reminders = compliance_reminder_repository.list_due_today(org_id, today=today.isoformat())
        sent = 0
        for rem in due_reminders:
            summary = f"{rem.get('compliance_code')} due on {rem.get('due_date')}"
            try:
                from app.modules.erp.tax.events.tax_events import emit_compliance_alert

                emit_compliance_alert(
                    org_id,
                    alert_type="compliance.deadline.approaching",
                    summary=summary,
                    severity="high",
                )
                emit_compliance_due(org_id, obligation_id=str(rem.get("obligation_id")), summary=summary)
            except Exception:
                pass
            compliance_reminder_repository.mark_sent(org_id, str(rem["id"]))
            sent += 1
        return {"processed": sent}


reminder_service = ReminderService()
