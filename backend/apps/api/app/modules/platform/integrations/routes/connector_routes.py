from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.schemas.connector_schema import ConnectorCreateRequest
from app.modules.platform.integrations.services.connector_service import connector_service

router = APIRouter()


@router.post("/connectors")
def create_connector(request: ConnectorCreateRequest, context=Depends(build_request_context)) -> dict:
    item = connector_service.create(
        context.org_id,
        connector_type=request.connector_type,
        provider_name=request.provider_name,
        config=request.config,
        credentials=request.credentials,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/connectors")
def list_connectors(context=Depends(build_request_context)) -> dict:
    items = connector_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}

