from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.platform.documents.schemas.evidence_schema import EvidenceLinkRequest
from app.modules.platform.documents.services.evidence_service import evidence_service

router = APIRouter(tags=["documents-evidence"])


@router.post("/evidence/links")
def link_evidence(request: EvidenceLinkRequest, context=Depends(build_request_context)) -> dict:
    item = evidence_service.link(
        context.org_id,
        document_id=request.document_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        workflow_id=request.workflow_id,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/evidence/links")
def list_evidence_links(
    context=Depends(build_request_context),
    entity_type: str = Query(...),
    entity_id: str = Query(...),
) -> dict:
    items = evidence_service.list_for_entity(context.org_id, entity_type=entity_type, entity_id=entity_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/evidence/links/bulk")
def bulk_link_evidence(requests: list[EvidenceLinkRequest], context=Depends(build_request_context)) -> dict:
    results: list[dict] = []
    for idx, req in enumerate(requests):
        try:
            item = evidence_service.link(
                context.org_id,
                document_id=req.document_id,
                entity_type=req.entity_type,
                entity_id=req.entity_id,
                workflow_id=req.workflow_id,
                metadata=req.metadata,
            )
            results.append({"index": idx, "status": "linked", "item": item})
        except Exception as exc:
            results.append({"index": idx, "status": "error", "error": str(exc)})
    return {"request_id": context.request_id, "results": results}
