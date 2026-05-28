from __future__ import annotations

from app.services.event_bus import event_bus


def emit_document_uploaded(org_id: str, *, document_id: str, document_type: str, storage_path: str) -> None:
    event_bus.publish(
        event_type="document.uploaded",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={
            "document_id": document_id,
            "document_type": document_type,
            "storage_path": storage_path,
        },
    )


def emit_duplicate_detected(org_id: str, *, document_id: str, matched_document_id: str) -> None:
    event_bus.publish(
        event_type="duplicate.detected",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id, "matched_document_id": matched_document_id},
    )
