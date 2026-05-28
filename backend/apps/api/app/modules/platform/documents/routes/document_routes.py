from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.platform.documents.schemas.document_schema import DocumentCreateRequest, DocumentVersionRequest
from app.modules.platform.documents.services.document_service import document_service

router = APIRouter(tags=["documents"])


@router.post("/documents")
def create_document(request: DocumentCreateRequest, context=Depends(build_request_context)) -> dict:
    item = document_service.create_document(
        context.org_id,
        uploaded_by=context.user_id,
        document_type=request.document_type,
        file_name=request.file_name,
        mime_type=request.mime_type,
        file_size=request.file_size,
        base64_content=request.base64_content,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/documents")
def list_documents(
    context=Depends(build_request_context),
    limit: int = Query(default=50, ge=1, le=200),
    document_type: str | None = Query(default=None),
) -> dict:
    items = document_service.list_documents(context.org_id, limit=limit, document_type=document_type)
    return {"request_id": context.request_id, "items": items}


@router.post("/documents/bulk")
def bulk_create_documents(requests: list[DocumentCreateRequest], context=Depends(build_request_context)) -> dict:
    results: list[dict] = []
    for idx, req in enumerate(requests):
        try:
            item = document_service.create_document(
                context.org_id,
                uploaded_by=context.user_id,
                document_type=req.document_type,
                file_name=req.file_name,
                mime_type=req.mime_type,
                file_size=req.file_size,
                base64_content=req.base64_content,
                metadata=req.metadata,
            )
            results.append({"index": idx, "status": "created", "item": item})
        except Exception as exc:
            results.append({"index": idx, "status": "error", "error": str(exc)})
    return {"request_id": context.request_id, "results": results}


@router.post("/documents/{document_id}/versions")
def create_document_version(document_id: str, request: DocumentVersionRequest, context=Depends(build_request_context)) -> dict:
    item = document_service.create_new_version(
        context.org_id,
        document_id=document_id,
        uploaded_by=context.user_id,
        file_name=request.file_name,
        mime_type=request.mime_type,
        file_size=request.file_size,
        base64_content=request.base64_content,
        change_reason=request.change_reason,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}
