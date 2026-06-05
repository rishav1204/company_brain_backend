from __future__ import annotations

from app.modules.erp.accounts_payable.engine.aging_engine import bucket_invoice
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository


class AgingService:
    def report(self, org_id: str, *, as_of_date: str | None = None) -> dict:
        outstanding = invoice_repository.list_outstanding(org_id)
        buckets: dict[str, list] = {"current": [], "1-30": [], "31-60": [], "61-90": [], "90+": []}
        totals: dict[str, float] = {k: 0.0 for k in buckets}
        for inv in outstanding:
            item = bucket_invoice(inv, as_of=as_of_date)
            b = str(item["bucket"])
            buckets[b].append(item)
            totals[b] += float(item["outstanding"])
        return {
            "as_of_date": as_of_date,
            "buckets": buckets,
            "totals": totals,
            "grand_total": sum(totals.values()),
        }


aging_service = AgingService()
