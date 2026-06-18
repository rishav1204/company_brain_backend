from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.account_resolver import resolve_receivable_account
from app.modules.erp.accounts_receivable.repositories.customer_balance_repository import customer_balance_repository
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository


class CustomerBalanceService:
    def refresh_customer(self, org_id: str, *, customer_id: str) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id) or {}
        receivable_id = resolve_receivable_account(org_id, customer)
        gl_outstanding = 0.0
        if receivable_id:
            gl_outstanding = customer_balance_repository.compute_gl_outstanding(
                org_id, customer_id=customer_id, receivable_account_id=receivable_id
            )
        invoices = ar_invoice_repository.list(org_id, customer_id=customer_id, limit=500)
        unposted = sum(
            max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
            for i in invoices
            if str(i.get("status")) in {"issued", "partially_paid", "overdue"} and not i.get("journal_id")
        )
        outstanding = max(gl_outstanding, 0.0) + unposted
        if outstanding <= 0:
            outstanding = sum(
                max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
                for i in invoices
                if str(i.get("status")) in {"issued", "partially_paid", "overdue"}
            )
        credit_limit = float(customer.get("credit_limit") or 0)
        return customer_balance_repository.upsert(
            org_id,
            customer_id=customer_id,
            outstanding_amount=outstanding,
            credit_used=outstanding if credit_limit > 0 else 0,
        )

    def list_balances(self, org_id: str) -> list[dict]:
        return customer_balance_repository.list(org_id)


customer_balance_service = CustomerBalanceService()
