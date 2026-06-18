from __future__ import annotations

from app.modules.erp.accounts_receivable.repositories.customer_balance_repository import customer_balance_repository
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository


class StatementService:
    def generate(self, org_id: str, *, customer_id: str, opening_balance: float = 0) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found")
        invoices = ar_invoice_repository.list(org_id, customer_id=customer_id, limit=500)
        receipts = receipt_repository.list(org_id, customer_id=customer_id, limit=500)
        invoice_total = sum(float(i.get("total_amount") or 0) for i in invoices if str(i.get("status")) not in {"cancelled", "draft"})
        receipt_total = sum(float(r.get("amount") or 0) for r in receipts if str(r.get("status")) == "completed")
        closing = round(opening_balance + invoice_total - receipt_total, 2)
        balance = customer_balance_repository.get(org_id, customer_id=customer_id)
        return {
            "customer_id": customer_id,
            "customer_name": customer.get("customer_name"),
            "opening_balance": opening_balance,
            "invoices_total": round(invoice_total, 2),
            "receipts_total": round(receipt_total, 2),
            "closing_balance": closing,
            "formula": "ClosingBalance = OpeningBalance + Invoices - Receipts",
            "projected_outstanding": balance,
            "line_items": {
                "invoices": invoices,
                "receipts": receipts,
            },
        }


statement_service = StatementService()
