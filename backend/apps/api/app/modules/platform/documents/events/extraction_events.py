from __future__ import annotations

from app.services.event_bus import event_bus


def emit_document_classified(org_id: str, *, document_id: str, classification: str, confidence: float) -> None:
    event_bus.publish(
        event_type="document.classified",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={
            "document_id": document_id,
            "classification": classification,
            "confidence": confidence,
        },
    )
