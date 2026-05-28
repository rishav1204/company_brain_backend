from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.schemas.sync_schema import SyncJobCreateRequest
from app.modules.platform.integrations.services.sync_service import sync_service

router = APIRouter()


@router.post("/sync/jobs")
def create_sync_job(request: SyncJobCreateRequest, context=Depends(build_request_context)) -> dict:
    item = sync_service.create_job(
        context.org_id,
        connector_id=request.connector_id,
        sync_type=request.sync_type,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/sync/jobs")
def list_sync_jobs(context=Depends(build_request_context)) -> dict:
    items = sync_service.list_jobs(context.org_id)
    return {"request_id": context.request_id, "items": items}

