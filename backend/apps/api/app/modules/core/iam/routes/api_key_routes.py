from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.repositories.api_key_repository import ApiKeyRepository
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.services.rbac_service import has_permission
from app.modules.core.iam.validators.permission_validator import validate_permission_key

router = APIRouter(tags=["iam-api-keys"])
api_key_repo = ApiKeyRepository()


class ApiKeyCreateRequest(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    idempotency_key: str | None = None


@router.get("/api-keys")
def list_api_keys(context=Depends(build_request_context)) -> dict:
    if not has_permission(context.org_id, context.user_id, "organization.manage"):
        if "tenant_admin" not in {r.lower() for r in context.roles}:
            raise HTTPException(status_code=403, detail="organization.manage required")
    rows = api_key_repo.list_keys(context.org_id)
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.99,
        "verification_status": "api_keys_listed",
    }


@router.post("/api-keys")
def create_api_key(body: ApiKeyCreateRequest, context=Depends(build_request_context)) -> dict:
    if not has_permission(context.org_id, context.user_id, "organization.manage"):
        if "tenant_admin" not in {r.lower() for r in context.roles}:
            raise HTTPException(status_code=403, detail="organization.manage required")
    check_idempotency("iam:api_key_create", context, body.idempotency_key)
    for scope in body.scopes:
        try:
            validate_permission_key(scope)
        except ValueError:
            if scope not in {"*", "admin"}:
                raise HTTPException(status_code=400, detail=f"Invalid API key scope: {scope}")
    row, raw_key = api_key_repo.create_key(
        org_id=context.org_id,
        name=body.name,
        scopes=body.scopes,
        created_by=context.user_id,
        expires_at=body.expires_at,
    )
    mark_idempotency("iam:api_key_create", context, body.idempotency_key)
    return {
        "request_id": context.request_id,
        "api_key": raw_key,
        "key": row,
        "confidence": 0.99,
        "verification_status": "api_key_created",
    }


@router.post("/api-keys/{key_id}/revoke")
def revoke_api_key(key_id: str, context=Depends(build_request_context)) -> dict:
    if not has_permission(context.org_id, context.user_id, "organization.manage"):
        if "tenant_admin" not in {r.lower() for r in context.roles}:
            raise HTTPException(status_code=403, detail="organization.manage required")
    if not api_key_repo.revoke_key(context.org_id, key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    return {
        "request_id": context.request_id,
        "status": "revoked",
        "key_id": key_id,
        "confidence": 0.99,
        "verification_status": "api_key_revoked",
    }
