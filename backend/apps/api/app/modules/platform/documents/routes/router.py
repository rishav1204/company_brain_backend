from fastapi import APIRouter

from app.modules.platform.documents.routes import (
    classification_routes,
    document_routes,
    evidence_routes,
    ocr_routes,
    pipeline_routes,
    preview_routes,
    review_routes,
    search_routes,
    upload_routes,
)

documents_router = APIRouter()
documents_router.include_router(document_routes.router)
documents_router.include_router(upload_routes.router)
documents_router.include_router(ocr_routes.router)
documents_router.include_router(classification_routes.router)
documents_router.include_router(evidence_routes.router)
documents_router.include_router(search_routes.router)
documents_router.include_router(preview_routes.router)
documents_router.include_router(review_routes.router)
documents_router.include_router(pipeline_routes.router)
