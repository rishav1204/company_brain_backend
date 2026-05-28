from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_invoice_created(
    org_id: str,
    *,
    invoice_id: str,
    amount: float | None = None,
    metadata: dict | None = None,
    trace_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.invoice.created",
        org_id=org_id,
        source="erp.ap",
        entity_type="invoice",
        entity_id=invoice_id,
        payload={"entity_type": "invoice", "entity_id": invoice_id, "amount": amount, **(metadata or {})},
        trace_id=trace_id,
        idempotency_key=idempotency_key,
    )


def emit_payment_completed(org_id: str, *, payment_id: str, amount: float | None = None, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.payment.completed",
        org_id=org_id,
        source="erp.treasury",
        entity_type="payment",
        entity_id=payment_id,
        payload={"entity_type": "payment", "entity_id": payment_id, "amount": amount},
        trace_id=trace_id,
    )


def emit_journal_posted(org_id: str, *, journal_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.journal.posted",
        org_id=org_id,
        source="erp.gl",
        entity_type="journal",
        entity_id=journal_id,
        payload={"entity_type": "journal", "entity_id": journal_id},
        trace_id=trace_id,
    )


def emit_invoice_approved(org_id: str, *, invoice_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.invoice.approved",
        org_id=org_id,
        source="erp.ap",
        entity_type="invoice",
        entity_id=invoice_id,
        payload={"entity_type": "invoice", "entity_id": invoice_id},
        trace_id=trace_id,
    )


def emit_invoice_updated(org_id: str, *, invoice_id: str, changes: dict | None = None, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.invoice.updated",
        org_id=org_id,
        source="erp.ap",
        entity_type="invoice",
        entity_id=invoice_id,
        payload={"entity_type": "invoice", "entity_id": invoice_id, "changes": changes or {}},
        trace_id=trace_id,
    )


def emit_payment_failed(org_id: str, *, payment_id: str, reason: str | None = None, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.payment.failed",
        org_id=org_id,
        source="erp.treasury",
        entity_type="payment",
        entity_id=payment_id,
        payload={"entity_type": "payment", "entity_id": payment_id, "reason": reason},
        trace_id=trace_id,
    )


def emit_journal_reversed(org_id: str, *, journal_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.journal.reversed",
        org_id=org_id,
        source="erp.gl",
        entity_type="journal",
        entity_id=journal_id,
        payload={"entity_type": "journal", "entity_id": journal_id},
        trace_id=trace_id,
    )


def emit_vendor_created(org_id: str, *, vendor_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.vendor.created",
        org_id=org_id,
        source="erp.ap",
        entity_type="vendor",
        entity_id=vendor_id,
        payload={"entity_type": "vendor", "entity_id": vendor_id},
        trace_id=trace_id,
    )


def emit_gst_return_generated(org_id: str, *, return_id: str, period: str | None = None, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.gst.return.generated",
        org_id=org_id,
        source="erp.compliance",
        entity_type="gst_return",
        entity_id=return_id,
        payload={"entity_type": "gst_return", "entity_id": return_id, "period": period},
        trace_id=trace_id,
    )


def emit_reconciliation_pending(org_id: str, *, reconciliation_id: str, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="erp.reconciliation.pending",
        org_id=org_id,
        source="erp.treasury",
        entity_type="reconciliation",
        entity_id=reconciliation_id,
        payload={"entity_type": "reconciliation", "entity_id": reconciliation_id},
        trace_id=trace_id,
    )
