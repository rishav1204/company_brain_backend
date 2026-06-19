from __future__ import annotations


def _publish(event_type: str, org_id: str, *, entity_id: str, payload: dict) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type=event_type,
            org_id=org_id,
            source="erp.ar",
            entity_type="ar",
            entity_id=entity_id,
            payload=payload,
        )
    except Exception:
        pass


def emit_sales_invoice_created(org_id: str, *, invoice_id: str, amount: float, customer_id: str) -> None:
    _publish("sales.invoice.created", org_id, entity_id=invoice_id, payload={
        "invoice_id": invoice_id, "amount": amount, "customer_id": customer_id,
    })


def emit_invoice_issued(org_id: str, *, invoice_id: str, amount: float, customer_id: str) -> None:
    _publish("invoice.issued", org_id, entity_id=invoice_id, payload={
        "invoice_id": invoice_id, "amount": amount, "customer_id": customer_id,
    })


def emit_invoice_overdue(org_id: str, *, invoice_id: str, due_date: str) -> None:
    _publish("invoice.overdue", org_id, entity_id=invoice_id, payload={
        "invoice_id": invoice_id, "due_date": due_date,
    })


def emit_collection_required(org_id: str, *, invoice_id: str, stage: str) -> None:
    _publish("collection.required", org_id, entity_id=invoice_id, payload={
        "invoice_id": invoice_id, "stage": stage,
    })


def emit_payment_received(org_id: str, *, receipt_id: str, amount: float, customer_id: str, bank_account_id: str | None = None, receipt_date: str | None = None, journal_id: str | None = None) -> None:
    _publish("payment.received", org_id, entity_id=receipt_id, payload={
        "receipt_id": receipt_id, "amount": amount, "customer_id": customer_id,
        "bank_account_id": bank_account_id, "receipt_date": receipt_date, "journal_id": journal_id,
    })


def emit_credit_limit_exceeded(org_id: str, *, customer_id: str, invoice_amount: float, available: float) -> None:
    _publish("customer.credit.limit.exceeded", org_id, entity_id=customer_id, payload={
        "customer_id": customer_id, "invoice_amount": invoice_amount, "available_credit": available,
    })
