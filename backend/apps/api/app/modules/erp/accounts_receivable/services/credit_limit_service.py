from __future__ import annotations

from app.modules.erp.accounts_receivable.engine.credit_control_engine import credit_check
from app.modules.erp.accounts_receivable.events.ar_events import emit_credit_limit_exceeded
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.services.customer_balance_service import customer_balance_service


class CreditLimitService:
    def check_before_issue(self, org_id: str, *, customer_id: str, invoice_amount: float) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found")
        balance = customer_balance_service.refresh_customer(org_id, customer_id=customer_id)
        outstanding = float(balance.get("outstanding_amount") or 0)
        result = credit_check(
            credit_limit=float(customer.get("credit_limit") or 0),
            outstanding=outstanding,
            invoice_amount=invoice_amount,
        )
        if result.get("exceeds_limit"):
            emit_credit_limit_exceeded(
                org_id,
                customer_id=customer_id,
                invoice_amount=invoice_amount,
                available=result.get("available_credit", 0),
            )
        return result


credit_limit_service = CreditLimitService()
