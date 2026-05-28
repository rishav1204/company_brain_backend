from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.repositories import permission_repo
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.schemas.permission_schema import PermissionListResponse, PermissionResponse
from app.modules.core.iam.services.rbac_service import has_permission
from app.modules.core.iam.validators.permission_validator import validate_permission_key

router = APIRouter(tags=["iam-permissions"])


def _require_permission_admin(context) -> None:
    if "tenant_admin" in {r.lower() for r in context.roles}:
        return
    if not has_permission(context.org_id, context.user_id, "org.admin"):
        raise HTTPException(status_code=403, detail="org.admin permission required")


class CreatePermissionRequest(BaseModel):
    resource: str
    action: str
    description: str | None = None
    idempotency_key: str | None = None


class UpdatePermissionRequest(BaseModel):
    description: str | None = None


@router.get("/permissions", response_model=PermissionListResponse)
def list_permissions(context=Depends(build_request_context)) -> PermissionListResponse:
    rows = permission_repo.list_permissions()
    items = [
        PermissionResponse(
            id=row["id"],
            resource=row["resource"],
            action=row["action"],
            permission_key=row["permission_key"],
            description=row.get("description"),
        )
        for row in rows
    ]
    return PermissionListResponse(
        request_id=context.request_id,
        items=items,
        confidence=0.99,
        verification_status="iam_permissions_listed",
    )


@router.post("/permissions")
def create_permission(body: CreatePermissionRequest, context=Depends(build_request_context)) -> dict:
    _require_permission_admin(context)
    check_idempotency("iam:permission_create", context, body.idempotency_key)
    key = f"{body.resource.strip().lower()}.{body.action.strip().lower()}"
    try:
        validate_permission_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = permission_repo.get_by_key(key)
    if existing:
        raise HTTPException(status_code=409, detail="Permission already exists")
    row = permission_repo.create_permission(body.resource, body.action, description=body.description)
    mark_idempotency("iam:permission_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "permission": row, "verification_status": "iam_permission_created"}


@router.patch("/permissions/{permission_id}")
def update_permission(
    permission_id: str,
    body: UpdatePermissionRequest,
    context=Depends(build_request_context),
) -> dict:
    _require_permission_admin(context)
    row = permission_repo.update_permission(permission_id, description=body.description)
    if not row:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"request_id": context.request_id, "permission": row, "verification_status": "iam_permission_updated"}
