from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.documents.events.extraction_events import emit_document_classified
from app.modules.platform.documents.schemas.extraction_schema import ClassificationRequest
from app.modules.platform.documents.services.classification_service import classification_service

router = APIRouter(tags=["documents-classification"])


@router.post("/documents/classify")
def classify_document(request: ClassificationRequest, context=Depends(build_request_context)) -> dict:
    row = classification_service.classify(context.org_id, document_id=request.document_id, hint=request.hint)
    emit_document_classified(
        context.org_id,
        document_id=request.document_id,
        classification=str(row.get("classification", "")),
        confidence=float(row.get("confidence_score", 0)),
    )
    return {"request_id": context.request_id, "item": row}
