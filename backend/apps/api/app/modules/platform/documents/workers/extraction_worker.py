from __future__ import annotations

from app.modules.platform.documents.services.ocr_service import ocr_service


def process_extraction_job(org_id: str, *, document_id: str, extraction_type: str) -> dict:
    return ocr_service.process_document(org_id, document_id=document_id, extraction_type=extraction_type)
