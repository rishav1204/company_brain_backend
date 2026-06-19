from __future__ import annotations

from app.modules.erp.banking.engine.bank_feed_engine import normalize_batch
from app.modules.erp.banking.events.banking_events import emit_bank_transaction_imported
from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
from app.modules.erp.banking.services.transaction_service import transaction_service
from app.modules.platform.integrations.services.connector_registry import connector_registry


class BankFeedService:
    def import_feed(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        provider: str = "stub_bank",
        payload: dict | None = None,
        transactions: list[dict] | None = None,
        source: str = "manual_import",
    ) -> dict:
        imported = 0
        skipped = 0
        if transactions:
            canonical = normalize_batch(transactions)
            for row in canonical:
                key = f"{bank_account_id}:{row.get('reference')}:{row.get('date')}:{row.get('amount')}:{row.get('type')}"
                if bank_transaction_repository.find_by_idempotency(org_id, import_idempotency_key=key):
                    skipped += 1
                    continue
                transaction_service.import_canonical(org_id, bank_account_id=bank_account_id, row=row, idempotency_key=key, source=source)
                imported += 1
        else:
            connector = connector_registry.resolve(connector_type="bank", provider_name=provider)
            if not connector:
                raise ValueError(f"Bank connector not found: {provider}")
            canonical_rows = connector.import_transactions(idempotency_key=f"{org_id}:{bank_account_id}", payload=payload or {})
            for tx in canonical_rows:
                row = normalize_batch([{
                    "date": str(tx.occurred_at or "")[:10],
                    "amount": float(tx.amount),
                    "type": "credit" if float(tx.amount) >= 0 else "debit",
                    "reference": tx.reference or tx.bank_tx_id,
                    "narration": tx.description,
                }])[0]
                key = tx.bank_tx_id
                if bank_transaction_repository.find_by_idempotency(org_id, import_idempotency_key=key):
                    skipped += 1
                    continue
                transaction_service.import_canonical(org_id, bank_account_id=bank_account_id, row=row, idempotency_key=key, source="bank_feed")
                imported += 1
        emit_bank_transaction_imported(org_id, bank_account_id=bank_account_id, count=imported)
        return {"imported": imported, "skipped": skipped, "bank_account_id": bank_account_id}


bank_feed_service = BankFeedService()
