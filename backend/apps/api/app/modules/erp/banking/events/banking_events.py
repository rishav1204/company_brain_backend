from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_bank_account_created(org_id: str, *, bank_account_id: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="bank.account.created", org_id=org_id, source="erp.banking", entity_type="bank_account", entity_id=bank_account_id, payload={"bank_account_id": bank_account_id}, trace_id=trace_id)


def emit_bank_statement_imported(org_id: str, *, import_id: str, bank_account_id: str, count: int, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="bank.statement.imported", org_id=org_id, source="erp.banking", entity_type="bank_statement_import", entity_id=import_id, payload={"import_id": import_id, "bank_account_id": bank_account_id, "imported_count": count}, trace_id=trace_id)


def emit_bank_transaction_imported(org_id: str, *, bank_account_id: str, count: int, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="bank.transaction.imported", org_id=org_id, source="erp.banking", entity_type="bank_account", entity_id=bank_account_id, payload={"bank_account_id": bank_account_id, "imported_count": count}, trace_id=trace_id)


def emit_payment_executed(org_id: str, *, payment_request_id: str, amount: float | None = None, journal_id: str | None = None, bank_transaction_id: str | None = None, ap_payment_id: str | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="payment.executed", org_id=org_id, source="erp.banking", entity_type="payment_request", entity_id=payment_request_id, payload={"payment_request_id": payment_request_id, "amount": amount, "journal_id": journal_id, "bank_transaction_id": bank_transaction_id, "ap_payment_id": ap_payment_id}, trace_id=trace_id)


def emit_payment_failed(org_id: str, *, payment_request_id: str, reason: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="payment.failed", org_id=org_id, source="erp.banking", entity_type="payment_request", entity_id=payment_request_id, payload={"payment_request_id": payment_request_id, "reason": reason}, trace_id=trace_id)


def emit_receipt_received(org_id: str, *, receipt_id: str, bank_account_id: str, amount: float, customer_id: str | None = None, journal_id: str | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(event_type="receipt.received", org_id=org_id, source="erp.banking", entity_type="ar_receipt", entity_id=receipt_id, payload={"receipt_id": receipt_id, "bank_account_id": bank_account_id, "amount": amount, "customer_id": customer_id, "journal_id": journal_id}, trace_id=trace_id)
