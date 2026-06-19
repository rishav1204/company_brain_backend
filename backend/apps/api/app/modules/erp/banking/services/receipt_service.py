from __future__ import annotations

from app.modules.erp.banking.events.banking_events import emit_receipt_received
from app.modules.erp.banking.services.bank_transaction_recorder import record_receipt_credit


class ReceiptService:
    def record(self, org_id: str, *, customer_id: str, bank_account_id: str, amount: float, receipt_date: str, payment_mode: str = "bank_transfer", reference: str | None = None) -> dict:
        from app.modules.erp.accounts_receivable.services.collection_service import collection_service
        return collection_service.record_receipt(org_id, customer_id=customer_id, bank_account_id=bank_account_id, amount=amount, receipt_date=receipt_date, payment_mode=payment_mode, reference=reference)

    def complete(self, org_id: str, *, receipt_id: str, completed_by: str, auto_post: bool = True) -> dict:
        from app.modules.erp.accounts_receivable.services.collection_service import collection_service
        result = collection_service.complete_receipt(org_id, receipt_id=receipt_id, completed_by=completed_by, auto_post=auto_post)
        receipt = result.get("receipt") or result
        bank_id = str(receipt.get("bank_account_id") or "")
        amount = float(receipt.get("amount") or 0)
        if bank_id and amount > 0:
            bank_tx = record_receipt_credit(org_id, bank_account_id=bank_id, amount=amount, reference=str(receipt.get("receipt_reference") or receipt_id), receipt_date=str(receipt.get("receipt_date") or "")[:10], idempotency_key=f"receipt:{receipt_id}", counterparty_ref=str(receipt.get("customer_id") or ""), source_id=receipt_id)
            result["bank_transaction_id"] = bank_tx.get("id")
        emit_receipt_received(org_id, receipt_id=receipt_id, bank_account_id=bank_id, amount=amount, customer_id=str(receipt.get("customer_id") or ""), journal_id=str(result.get("journal_id") or ""))
        return result

    def list(self, org_id: str, *, customer_id: str | None = None) -> list[dict]:
        from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository
        return receipt_repository.list(org_id, customer_id=customer_id)


receipt_service = ReceiptService()
