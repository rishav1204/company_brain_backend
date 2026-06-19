from __future__ import annotations

from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository


class TransactionService:
    def import_canonical(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        row: dict,
        idempotency_key: str | None = None,
        source: str = "statement_import",
    ) -> dict:
        amount = float(row.get("amount") or 0)
        if amount == 0:
            raise ValueError("Amount cannot be zero")
        tx_type = str(row.get("type") or "debit")
        key = idempotency_key or f"{bank_account_id}:{row.get('reference')}:{row.get('date')}:{amount}:{tx_type}"
        existing = bank_transaction_repository.find_by_idempotency(org_id, import_idempotency_key=key)
        if existing:
            return existing
        return bank_transaction_repository.create(
            org_id,
            bank_account_id=bank_account_id,
            transaction_reference=str(row.get("reference") or key)[:128],
            transaction_date=str(row.get("date"))[:10],
            amount=amount,
            transaction_type=tx_type,
            currency_code="INR",
            description=str(row.get("narration") or ""),
            source=source,
            import_idempotency_key=key,
            value_date=str(row.get("date"))[:10],
            status="imported",
        )

    def list_transactions(self, org_id: str, *, bank_account_id: str | None = None, reconciliation_status: str | None = None) -> list[dict]:
        return bank_transaction_repository.list(org_id, bank_account_id=bank_account_id, reconciliation_status=reconciliation_status)

    def get_transaction(self, org_id: str, *, transaction_id: str) -> dict:
        row = bank_transaction_repository.get(org_id, transaction_id=transaction_id)
        if not row:
            raise ValueError("Transaction not found")
        return row


transaction_service = TransactionService()
