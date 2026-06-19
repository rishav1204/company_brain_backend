from __future__ import annotations


class CustomerMatchService:
    def collect_candidates(self, org_id: str) -> list[dict]:
        candidates: list[dict] = []
        try:
            from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository

            for r in receipt_repository.list(org_id, limit=200):
                if str(r.get("status")) != "completed":
                    continue
                candidates.append({
                    "id": r.get("id"),
                    "target_type": "ar_receipt",
                    "amount": float(r.get("amount") or 0),
                    "date": r.get("receipt_date"),
                    "reference": r.get("receipt_reference"),
                    "counterparty_ref": r.get("customer_id"),
                })
        except Exception:
            pass
        try:
            from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

            for inv in ar_invoice_repository.list_outstanding(org_id):
                outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
                if outstanding > 0:
                    candidates.append({
                        "id": inv.get("id"),
                        "target_type": "ar_invoice",
                        "amount": outstanding,
                        "date": inv.get("due_date") or inv.get("invoice_date"),
                        "reference": inv.get("invoice_number"),
                        "counterparty_ref": inv.get("customer_id"),
                    })
        except Exception:
            pass
        return candidates

    def customer_summary(self, org_id: str, *, customer_id: str) -> dict:
        receipts: list[dict] = []
        invoices: list[dict] = []
        try:
            from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository

            for r in receipt_repository.list(org_id, limit=500):
                if str(r.get("customer_id")) == customer_id:
                    receipts.append(r)
        except Exception:
            pass
        try:
            from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

            for inv in ar_invoice_repository.list_outstanding(org_id):
                if str(inv.get("customer_id")) == customer_id:
                    invoices.append(inv)
        except Exception:
            pass
        total_outstanding = sum(
            max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0)) for i in invoices
        )
        return {
            "customer_id": customer_id,
            "receipts": receipts,
            "outstanding_invoices": invoices,
            "total_outstanding": round(total_outstanding, 2),
        }


customer_match_service = CustomerMatchService()
