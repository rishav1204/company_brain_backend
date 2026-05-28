from __future__ import annotations

from app.modules.platform.documents.events.ocr_events import emit_ocr_completed
from app.modules.platform.documents.services.ocr_service import ocr_service


def process_ocr_job(org_id: str, *, document_id: str, extraction_type: str = "invoice_ocr") -> dict:
    result = ocr_service.process_document(org_id, document_id=document_id, extraction_type=extraction_type)
    extraction_id = str((result.get("extraction") or {}).get("id", ""))
    if extraction_id:
        emit_ocr_completed(org_id, document_id=document_id, extraction_id=extraction_id)
    return result
