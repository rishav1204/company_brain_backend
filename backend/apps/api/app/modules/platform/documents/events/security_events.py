from __future__ import annotations

from app.services.event_bus import event_bus


def emit_malware_scan_requested(org_id: str, *, document_id: str) -> None:
    event_bus.publish(
        event_type="document.malware_scan.requested",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id},
    )


def emit_malware_scan_completed(org_id: str, *, document_id: str, status: str) -> None:
    event_bus.publish(
        event_type="document.malware_scan.completed",
        org_id=org_id,
        source="documents",
        trace_id="",
        entity_type="document",
        entity_id=document_id,
        payload={"document_id": document_id, "status": status},
    )

