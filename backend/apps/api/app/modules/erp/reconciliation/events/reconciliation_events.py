from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_reconciliation_suggested(org_id: str, *, reconciliation_id: str, confidence: float, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reconciliation.suggested",
        org_id=org_id,
        source="erp.reconciliation",
        entity_type="reconciliation",
        entity_id=reconciliation_id,
        payload={"reconciliation_id": reconciliation_id, "confidence_score": confidence},
        trace_id=trace_id,
    )


def emit_reconciliation_completed(
    org_id: str,
    *,
    reconciliation_id: str,
    bank_transaction_id: str,
    ledger_entry_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reconciliation.completed",
        org_id=org_id,
        source="erp.reconciliation",
        entity_type="reconciliation",
        entity_id=reconciliation_id,
        payload={
            "reconciliation_id": reconciliation_id,
            "bank_transaction_id": bank_transaction_id,
            "ledger_entry_id": ledger_entry_id,
        },
        trace_id=trace_id,
    )


def emit_reconciliation_exception_created(
    org_id: str,
    *,
    exception_id: str,
    exception_type: str,
    bank_transaction_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reconciliation.exception.created",
        org_id=org_id,
        source="erp.reconciliation",
        entity_type="reconciliation_exception",
        entity_id=exception_id,
        payload={"exception_id": exception_id, "exception_type": exception_type, "bank_transaction_id": bank_transaction_id},
        trace_id=trace_id,
    )


def emit_reconciliation_adjustment_required(
    org_id: str,
    *,
    adjustment_id: str,
    amount: float,
    adjustment_type: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reconciliation.adjustment.required",
        org_id=org_id,
        source="erp.reconciliation",
        entity_type="reconciliation_adjustment",
        entity_id=adjustment_id,
        payload={"adjustment_id": adjustment_id, "amount": amount, "adjustment_type": adjustment_type},
        trace_id=trace_id,
    )


def emit_reconciliation_adjustment_posted(
    org_id: str,
    *,
    adjustment_id: str,
    journal_id: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="reconciliation.adjustment.posted",
        org_id=org_id,
        source="erp.reconciliation",
        entity_type="reconciliation_adjustment",
        entity_id=adjustment_id,
        payload={"adjustment_id": adjustment_id, "journal_id": journal_id},
        trace_id=trace_id,
    )
