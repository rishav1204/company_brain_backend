from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
from app.modules.platform.documents.schemas.extraction_schema import ExtractionCorrectionRequest
from app.modules.platform.documents.services.versioning_service import versioning_service

router = APIRouter(tags=["documents-review"])


@router.post("/documents/extractions/correct")
def correct_extraction(request: ExtractionCorrectionRequest, context=Depends(build_request_context)) -> dict:
    """
    Human correction loop:
    - store corrected extraction as a new extraction row (immutable history)
    - create a new document version (same storage_path) to mark review milestone + audit metadata
    """
    doc = document_repository.get_document(context.org_id, request.document_id)
    if not doc:
        raise ValueError("Document not found")

    row = extraction_repository.create_extraction(
        context.org_id,
        document_id=request.document_id,
        extraction_type="human_correction",
        extracted_data={
            **(request.corrected_data or {}),
            "reviewer_notes": request.reviewer_notes,
            "corrected_by": context.user_id,
        },
        confidence_score=1.0,
        extraction_status="corrected",
    )

    version = versioning_service.create_version(
        context.org_id,
        document_id=request.document_id,
        storage_path=str(doc.get("storage_path", "")),
        uploaded_by=context.user_id,
        change_reason="extraction_correction",
        metadata={"extraction_id": str(row.get("id", "")), "reviewer_notes": request.reviewer_notes},
    )
    return {"request_id": context.request_id, "item": {"extraction": row, "version": version}}

