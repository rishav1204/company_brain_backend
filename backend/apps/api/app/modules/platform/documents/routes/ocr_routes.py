from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.documents.events.ocr_events import emit_ocr_requested
from app.modules.platform.documents.schemas.extraction_schema import OCRRequest
from app.modules.platform.documents.services.ocr_service import ocr_service

router = APIRouter(tags=["documents-ocr"])


@router.post("/ocr/request")
def request_ocr(request: OCRRequest, context=Depends(build_request_context)) -> dict:
    emit_ocr_requested(context.org_id, document_id=request.document_id, extraction_type=request.extraction_type)
    return {"request_id": context.request_id, "queued": True}


@router.post("/ocr/process")
def process_ocr_now(request: OCRRequest, context=Depends(build_request_context)) -> dict:
    result = ocr_service.process_document(
        context.org_id,
        document_id=request.document_id,
        extraction_type=request.extraction_type,
    )
    return {"request_id": context.request_id, "result": result}
