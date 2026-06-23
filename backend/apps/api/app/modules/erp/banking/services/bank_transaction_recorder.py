from __future__ import annotations

from datetime import date

from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository


def record_payment_debit(
    org_id: str,
    *,
    bank_account_id: str,
    amount: float,
    reference: str,
    payment_date: str | None = None,
    description: str | None = None,
    idempotency_key: str,
    counterparty_ref: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
) -> dict:
    existing = bank_transaction_repository.find_by_idempotency(org_id, import_idempotency_key=idempotency_key)
    if existing:
        return existing
    return bank_transaction_repository.create(
        org_id,
        bank_account_id=bank_account_id,
        transaction_reference=reference,
        transaction_date=(payment_date or date.today().isoformat())[:10],
        amount=amount,
        transaction_type="debit",
        currency_code="INR",
        description=description or f"Payment {reference}",
        source="api",
        counterparty_ref=counterparty_ref,
        import_idempotency_key=idempotency_key,
        metadata={"recorded_by": "banking_payment"},
        status="posted",
        source_type=source_type,
        source_id=source_id,
    )


def record_payment_debit_conn(
    conn,
    org_id: str,
    *,
    bank_account_id: str,
    amount: float,
    reference: str,
    payment_date: str | None = None,
    description: str | None = None,
    idempotency_key: str,
    counterparty_ref: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
) -> dict:
    existing = bank_transaction_repository.find_by_idempotency_conn(
        conn, org_id, import_idempotency_key=idempotency_key
    )
    if existing:
        return existing
    return bank_transaction_repository.create_conn(
        conn,
        org_id,
        bank_account_id=bank_account_id,
        transaction_reference=reference,
        transaction_date=(payment_date or date.today().isoformat())[:10],
        amount=amount,
        transaction_type="debit",
        currency_code="INR",
        description=description or f"Payment {reference}",
        source="api",
        counterparty_ref=counterparty_ref,
        import_idempotency_key=idempotency_key,
        metadata={"recorded_by": "banking_payment"},
        status="posted",
        source_type=source_type or "ap_payment",
        source_id=source_id,
    )


def record_receipt_credit(
    org_id: str,
    *,
    bank_account_id: str,
    amount: float,
    reference: str,
    receipt_date: str | None = None,
    description: str | None = None,
    idempotency_key: str,
    counterparty_ref: str | None = None,
    source_type: str = "ar_receipt",
    source_id: str | None = None,
) -> dict:
    existing = bank_transaction_repository.find_by_idempotency(org_id, import_idempotency_key=idempotency_key)
    if existing:
        return existing
    return bank_transaction_repository.create(
        org_id,
        bank_account_id=bank_account_id,
        transaction_reference=reference,
        transaction_date=(receipt_date or date.today().isoformat())[:10],
        amount=amount,
        transaction_type="credit",
        currency_code="INR",
        description=description or f"Receipt {reference}",
        source="payment_gateway",
        counterparty_ref=counterparty_ref,
        import_idempotency_key=idempotency_key,
        metadata={"recorded_by": "banking_receipt"},
        status="posted",
        source_type=source_type,
        source_id=source_id,
    )


def record_receipt_credit_conn(
    conn,
    org_id: str,
    *,
    bank_account_id: str,
    amount: float,
    reference: str,
    receipt_date: str | None = None,
    description: str | None = None,
    idempotency_key: str,
    counterparty_ref: str | None = None,
    source_type: str = "ar_receipt",
    source_id: str | None = None,
) -> dict:
    existing = bank_transaction_repository.find_by_idempotency_conn(
        conn, org_id, import_idempotency_key=idempotency_key
    )
    if existing:
        return existing
    return bank_transaction_repository.create_conn(
        conn,
        org_id,
        bank_account_id=bank_account_id,
        transaction_reference=reference,
        transaction_date=(receipt_date or date.today().isoformat())[:10],
        amount=amount,
        transaction_type="credit",
        currency_code="INR",
        description=description or f"Receipt {reference}",
        source="payment_gateway",
        counterparty_ref=counterparty_ref,
        import_idempotency_key=idempotency_key,
        metadata={"recorded_by": "banking_receipt"},
        status="posted",
        source_type=source_type,
        source_id=source_id,
    )
