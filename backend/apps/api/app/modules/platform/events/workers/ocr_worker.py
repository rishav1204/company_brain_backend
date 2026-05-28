from __future__ import annotations

from app.services.logger import log_event


def process_ocr_event(envelope: dict) -> dict:
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    document_id = payload.get("document_id") or envelope.get("entity_id")
    log_event(
        "platform.ocr.processed",
        org_id=org_id,
        event_type=event_type,
        document_id=document_id,
        entity_id=payload.get("entity_id"),
    )
    if event_type == "ai.ocr.requested" and org_id and document_id:
        try:
            extraction_type = str(payload.get("extraction_type", "invoice_ocr"))
            from app.modules.platform.documents.workers.ocr_worker import process_ocr_job

            doc_result = process_ocr_job(org_id, document_id=str(document_id), extraction_type=extraction_type)
            from app.modules.platform.governance.explainability.evidence_linker import auto_link_entity_evidence

            auto_link_entity_evidence(
                org_id,
                entity_type="document",
                entity_id=str(document_id),
                evidence_type="ocr_job",
                evidence_ref=str(document_id),
            )
            from app.modules.platform.events.events.ai_events import emit_invoice_ai_reviewed

            emit_invoice_ai_reviewed(
                org_id,
                invoice_id=str(document_id),
                review={"status": "ocr_completed", "document_id": document_id, "result": doc_result},
                trace_id=str(envelope.get("trace_id", "")) or None,
            )
        except Exception as exc:
            log_event("platform.ocr.followup_failed", org_id=org_id, error=str(exc))
    return {"status": "completed", "detail": "ocr_job_processed", "document_id": document_id}
