from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.services.storage_service import storage_service

router = APIRouter(tags=["documents-previews"])


@router.get("/documents/{document_id}/previews")
def get_document_previews(document_id: str, context=Depends(build_request_context)) -> dict:
    doc = document_repository.get_document(context.org_id, document_id=document_id)
    previews = storage_service.preview_urls(
        str(doc.get("storage_path", "")),
        mime_type=str(doc.get("mime_type", "")),
        expires_in_seconds=900,
    )
    return {"request_id": context.request_id, "item": {"document_id": document_id, **previews}}

