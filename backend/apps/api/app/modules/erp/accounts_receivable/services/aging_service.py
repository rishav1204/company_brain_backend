from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.aging_engine import bucket_invoice
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository


class AgingService:
    def report(self, org_id: str, *, as_of: str | None = None, customer_id: str | None = None) -> dict:
        invoices = ar_invoice_repository.list_outstanding(org_id)
        if customer_id:
            invoices = [i for i in invoices if str(i.get("customer_id")) == customer_id]
        bucketed = [bucket_invoice(i, as_of=as_of) for i in invoices]
        summary: dict[str, float] = {
            "current": 0, "1-30": 0, "31-60": 0, "61-90": 0, "90+": 0, "180+": 0, "365+": 0,
        }
        for inv in bucketed:
            summary[inv["bucket"]] = summary.get(inv["bucket"], 0) + float(inv.get("outstanding") or 0)
        return {
            "as_of": as_of,
            "buckets": {k: round(v, 2) for k, v in summary.items()},
            "invoices": bucketed,
            "total_outstanding": round(sum(summary.values()), 2),
        }


aging_service = AgingService()
