from __future__ import annotations

from datetime import date

from app.modules.erp.accounts_receivable.engine.aging_engine import aging_days
from app.modules.erp.accounts_receivable.engine.dunning_engine import determine_dunning_action
from app.modules.erp.accounts_receivable.events.ar_events import emit_collection_required, emit_invoice_overdue
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.services.ar_realtime_service import ar_realtime_service


class DunningService:
    def process_due_invoices(self, org_id: str) -> list[dict]:
        today = date.today().isoformat()
        actions: list[dict] = []
        for inv in ar_invoice_repository.list_outstanding(org_id):
            iid = str(inv.get("id"))
            due = str(inv.get("due_date") or "")[:10]
            days = aging_days(due_date=due, as_of=today)
            if days > 0 and str(inv.get("status")) != "overdue":
                ar_invoice_repository.set_status(org_id, invoice_id=iid, status="overdue")
                emit_invoice_overdue(org_id, invoice_id=iid, due_date=due)
            action = determine_dunning_action(aging_days=days)
            if not action:
                continue
            emit_collection_required(org_id, invoice_id=iid, stage=action["stage"])
            ar_realtime_service.push_collection_reminder(org_id, invoice_id=iid, stage=action["stage"])
            actions.append({"invoice_id": iid, **action})
        return actions


dunning_service = DunningService()
