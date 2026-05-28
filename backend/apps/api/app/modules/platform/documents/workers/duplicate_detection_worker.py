from __future__ import annotations

from app.modules.platform.documents.services.duplicate_detection_service import duplicate_detection_service


def process_duplicate_detection_job(org_id: str, *, document_id: str) -> dict | None:
    return duplicate_detection_service.detect(org_id, document_id=document_id)
