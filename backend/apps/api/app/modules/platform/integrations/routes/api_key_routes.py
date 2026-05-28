from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.integrations.schemas.api_key_schema import ApiKeyCreateRequest
from app.modules.platform.integrations.services.api_key_service import api_key_service

router = APIRouter()


@router.post("/api-keys")
def create_api_key(request: ApiKeyCreateRequest, context=Depends(build_request_context)) -> dict:
    item, raw_key = api_key_service.create(
        context.org_id,
        name=request.name,
        scopes=request.scopes,
    )
    return {"request_id": context.request_id, "item": item, "api_key": raw_key}


@router.get("/api-keys")
def list_api_keys(context=Depends(build_request_context)) -> dict:
    items = api_key_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/api-keys/{api_key_id}/revoke")
def revoke_api_key(api_key_id: str, context=Depends(build_request_context)) -> dict:
    item = api_key_service.revoke(context.org_id, api_key_id=api_key_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/api-keys/{api_key_id}/rotate")
def rotate_api_key(api_key_id: str, context=Depends(build_request_context)) -> dict:
    item, raw_key = api_key_service.rotate(context.org_id, api_key_id=api_key_id)
    return {"request_id": context.request_id, "item": item, "api_key": raw_key}

