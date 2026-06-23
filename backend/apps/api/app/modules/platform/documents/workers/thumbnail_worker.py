from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.services.storage_service import storage_service
from app.services.logger import log_event


def process_thumbnail_job(org_id: str, *, document_id: str) -> dict:
    doc = document_repository.get(org_id, document_id=document_id)
    if not doc:
        log_event("documents.thumbnail.missing", org_id=org_id, document_id=document_id)
        return {"status": "failed", "org_id": org_id, "document_id": document_id, "detail": "document_not_found"}
    storage_path = str(doc.get("storage_path") or "")
    mime_type = str(doc.get("mime_type") or "application/octet-stream")
    if not storage_path:
        return {"status": "skipped", "org_id": org_id, "document_id": document_id, "thumbnail": None, "detail": "no_storage_path"}
    try:
        previews = storage_service.preview_urls(storage_path, mime_type=mime_type)
        thumb = previews.get("thumbnail_url")
        return {
            "status": "completed",
            "org_id": org_id,
            "document_id": document_id,
            "thumbnail": thumb,
            "preview_url": previews.get("preview_url"),
        }
    except Exception as exc:
        log_event("documents.thumbnail.error", org_id=org_id, document_id=document_id, detail=str(exc))
        return {"status": "error", "org_id": org_id, "document_id": document_id, "detail": str(exc)}
