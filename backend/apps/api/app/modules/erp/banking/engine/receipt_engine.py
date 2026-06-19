from __future__ import annotations


def receipt_journal_metadata(*, receipt_id: str, bank_account_id: str, customer_id: str | None) -> dict:
    return {"receipt_id": receipt_id, "bank_account_id": bank_account_id, "customer_id": customer_id}
