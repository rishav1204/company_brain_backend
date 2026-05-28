from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.core.config import settings
from app.modules.platform.documents.schemas.document_schema import (
    CloudinaryDirectUploadSignRequest,
    CloudinaryFinalizeRequest,
    DocumentCreateRequest,
)
from app.modules.platform.documents.services.document_service import document_service
from app.services.event_queue import event_queue

router = APIRouter(tags=["documents-uploads"])

class CloudinarySignResponse(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    resource_type: str
    public_id: str
    signature: str
    upload_preset: str | None = None


@router.post("/uploads/documents")
def upload_document(request: DocumentCreateRequest, context=Depends(build_request_context)) -> dict:
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


@router.post("/uploads/cloudinary/sign-batch")
def sign_cloudinary_upload_batch(requests: list[CloudinaryDirectUploadSignRequest], context=Depends(build_request_context)) -> dict:
    results: list[dict] = []
    for idx, req in enumerate(requests):
        try:
            signed = sign_cloudinary_upload(req, context)
            results.append({"index": idx, "status": "ok", "item": signed.get("item")})
        except Exception as exc:
            results.append({"index": idx, "status": "error", "error": str(exc)})
    return {"request_id": context.request_id, "results": results}


@router.get("/uploads/cloudinary/resumable-config")
def resumable_upload_config(context=Depends(build_request_context)) -> dict:
    # Client-side resumable uploads are handled by Cloudinary SDK; we provide recommended settings.
    return {
        "request_id": context.request_id,
        "item": {
            "provider": "cloudinary",
            "chunk_size_bytes": 5 * 1024 * 1024,
            "max_file_size_bytes": 200 * 1024 * 1024,
            "finalize_endpoint": f"{settings.api_prefix}/uploads/cloudinary/finalize",
            "sign_endpoint": f"{settings.api_prefix}/uploads/cloudinary/sign",
        },
    }


@router.post("/uploads/cloudinary/sign")
def sign_cloudinary_upload(request: CloudinaryDirectUploadSignRequest, context=Depends(build_request_context)) -> dict:
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
        return {"request_id": context.request_id, "error": "Cloudinary not configured"}
    # Backpressure: avoid accepting unbounded uploads when OCR queue is heavily backlogged.
    if event_queue.lag(settings.queue_ai_ocr) > 1000:
        return {"request_id": context.request_id, "error": "OCR pipeline busy; try again shortly"}
    import cloudinary
    from cloudinary.utils import api_sign_request

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=settings.cloudinary_secure,
    )
    timestamp = int(datetime.now(timezone.utc).timestamp())
    folder = f"{settings.documents_bucket_prefix}/{context.org_id}/{request.document_type}/{datetime.now(timezone.utc):%Y/%m/%d}"
    resource_type = "image" if request.mime_type.lower().startswith("image/") else "raw"
    safe_base = request.file_name.rsplit(".", 1)[0].replace("\\", "_").replace("/", "_").strip() or "document"
    # Enforce org isolation and server-defined public_id.
    public_id = f"{folder}/{safe_base}-{timestamp}"
    params_to_sign = {"timestamp": timestamp, "folder": folder, "public_id": public_id}
    if settings.cloudinary_upload_preset:
        params_to_sign["upload_preset"] = settings.cloudinary_upload_preset
    signature = api_sign_request(params_to_sign, settings.cloudinary_api_secret)
    resp = CloudinarySignResponse(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        timestamp=timestamp,
        folder=folder,
        resource_type=resource_type,
        public_id=public_id,
        signature=signature,
        upload_preset=settings.cloudinary_upload_preset or None,
    )
    return {"request_id": context.request_id, "item": resp.model_dump()}


@router.post("/uploads/cloudinary/finalize")
def finalize_cloudinary_upload(request: CloudinaryFinalizeRequest, context=Depends(build_request_context)) -> dict:
    item = document_service.finalize_cloudinary_upload(
        context.org_id,
        uploaded_by=context.user_id,
        document_type=request.document_type,
        file_name=request.file_name,
        mime_type=request.mime_type,
        file_size=request.file_size,
        checksum_hash=request.checksum_hash,
        resource_type=request.resource_type,
        public_id=request.public_id,
        secure_url=request.secure_url,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}
