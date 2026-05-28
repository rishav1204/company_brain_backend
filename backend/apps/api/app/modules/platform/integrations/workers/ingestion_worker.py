from __future__ import annotations

from app.services.logger import log_event


def process_ingestion_job(envelope: dict) -> dict:
    """
    Worker entrypoint for ingestion records (email/webhook/external ERP).
    For now, this is a stub that simply acknowledges; email ingestion will
    later enqueue Module 6 document creation + OCR.
    """
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    source_type = str(payload.get("source_type") or "")
    log_event("integrations.ingestion.job", org_id=org_id, event_type=event_type)
    if source_type == "email":
        # Minimal pipeline: create document placeholders from provided attachments.
        try:
            from app.modules.platform.documents.services.document_service import document_service
        except Exception:
            return {"status": "error", "detail": "documents_module_unavailable"}

        attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
        created: list[dict] = []
        for a in attachments[:10]:
            if not isinstance(a, dict):
                continue
            try:
                created.append(
                    document_service.create_document(
                        org_id,
                        uploaded_by="email_ingestion",
                        document_type=str(a.get("document_type") or "invoice"),
                        file_name=str(a.get("file_name") or "email_attachment.bin"),
                        mime_type=str(a.get("mime_type") or "application/pdf"),
                        file_size=int(a.get("file_size") or 0),
                        base64_content=str(a.get("base64_content") or ""),
                        metadata={"source": "email", "message_id": payload.get("message_id")},
                        enqueue_ocr=True,
                    )
                )
            except Exception:
                continue
        return {"status": "processed", "created": len(created)}
    return {"status": "acknowledged"}

