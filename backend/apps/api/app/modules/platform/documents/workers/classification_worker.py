from __future__ import annotations

from app.modules.platform.documents.services.classification_service import classification_service


def process_classification_job(org_id: str, *, document_id: str, hint: str | None = None) -> dict:
    return classification_service.classify(org_id, document_id=document_id, hint=hint)
