from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_invoice_ai_reviewed(org_id: str, *, invoice_id: str, review: dict, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="invoice.ai.reviewed",
        org_id=org_id,
        source="ai.runtime",
        entity_type="invoice",
        entity_id=invoice_id,
        payload={"invoice_id": invoice_id, "review": review},
        trace_id=trace_id,
    )


def emit_ocr_requested(
    org_id: str,
    *,
    document_id: str,
    source: str = "ingestion",
    trace_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    return platform_event_service.publish(
        event_type="ai.ocr.requested",
        org_id=org_id,
        source="ingestion",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id, "source": source},
        trace_id=trace_id,
        idempotency_key=idempotency_key,
    )


def emit_risk_detected(org_id: str, *, entity_type: str, entity_id: str, risk: dict, trace_id: str | None = None) -> dict:
    return platform_event_service.publish(
        event_type="payment.risk.detected",
        org_id=org_id,
        source="ai.runtime",
        entity_type=entity_type,
        entity_id=entity_id,
        payload={"risk": risk, "summary": str(risk)},
        trace_id=trace_id,
    )


def emit_reconciliation_suggested(
    org_id: str, *, entity_id: str, summary: str, trace_id: str | None = None
) -> dict:
    return platform_event_service.publish(
        event_type="ai.reconciliation.suggested",
        org_id=org_id,
        source="ai.runtime",
        entity_type="reconciliation",
        entity_id=entity_id,
        payload={"summary": summary, "entity_label": entity_id},
        trace_id=trace_id,
    )
