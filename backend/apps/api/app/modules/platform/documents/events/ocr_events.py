from __future__ import annotations

from app.services.event_bus import event_bus


def emit_ocr_requested(org_id: str, *, document_id: str, extraction_type: str = "invoice_ocr") -> None:
    event_bus.publish(
        event_type="ai.ocr.requested",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id, "extraction_type": extraction_type},
    )


def emit_ocr_completed(org_id: str, *, document_id: str, extraction_id: str) -> None:
    event_bus.publish(
        event_type="ocr.completed",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id, "extraction_id": extraction_id},
    )
