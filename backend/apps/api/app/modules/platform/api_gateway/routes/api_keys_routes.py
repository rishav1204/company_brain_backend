from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.platform.api_gateway.engine.api_gateway_engine import api_gateway_engine
from app.modules.platform.api_gateway.schemas.gateway_schema import ApiKeyCreateRequest
from app.modules.platform.api_gateway.services.api_key_service import api_key_service

router = APIRouter()


@router.post("/api-keys")
def create_api_key(request: ApiKeyCreateRequest, context=Depends(build_request_context)) -> dict:
    def handler() -> dict:
        item, raw_key = api_key_service.create(
            context.org_id,
            name=request.name,
            scopes=request.scopes,
            key_tier=request.key_tier,
            ip_allowlist=request.ip_allowlist,
            rate_limit_per_minute=request.rate_limit_per_minute,
            rate_limit_per_hour=request.rate_limit_per_hour,
        )
        return {"request_id": context.request_id, "item": item, "api_key": raw_key}

    return api_gateway_engine.process_external_request(
        context,
        action="api.key.create",
        method="POST",
        path="/platform/api-keys",
        handler=handler,
        required_scopes=["api.keys.manage", "admin"],
    )


@router.get("/api-keys")
def list_api_keys(context=Depends(build_request_context)) -> dict:
    items = api_key_service.list(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.delete("/api-keys/{api_key_id}")
def revoke_api_key(api_key_id: str, context=Depends(build_request_context)) -> dict:
    def handler() -> dict:
        item = api_key_service.revoke(context.org_id, api_key_id=api_key_id)
        return {"request_id": context.request_id, "item": item}

    return api_gateway_engine.process_external_request(
        context,
        action="api.key.revoke",
        method="DELETE",
        path=f"/platform/api-keys/{api_key_id}",
        handler=handler,
        required_scopes=["api.keys.manage", "admin"],
    )
