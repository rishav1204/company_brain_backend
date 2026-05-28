from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.schemas.ingestion_schema import IngestionCreateRequest
from app.modules.platform.integrations.services.ingestion_service import ingestion_service

router = APIRouter()


@router.post("/ingestion")
def create_ingestion_record(request: IngestionCreateRequest, context=Depends(build_request_context)) -> dict:
    item = ingestion_service.create(
        context.org_id,
        source_type=request.source_type,
        source_reference=request.source_reference,
        payload=request.payload,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/ingestion")
def list_ingestion_records(context=Depends(build_request_context)) -> dict:
    items = ingestion_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}

