from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from pydantic import BaseModel, Field

from app.modules.core.iam.events.role_events import emit_role_assigned
from app.modules.core.iam.events.user_events import emit_user_created
from app.modules.core.iam.repositories import role_repo, user_repo
from app.modules.core.iam.schemas.user_schema import AssignRoleRequest, UserListResponse, UserResponse
from app.modules.core.iam.services.password_service import hash_password
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.services.api_key_auth_service import scope_allows
from app.modules.core.iam.services.rbac_service import has_permission
from app.modules.core.iam.validators.password_validator import validate_password_strength

class CreateUserRequest(BaseModel):
    email: str
    password: str
    display_name: str
    role_name: str = "analyst"
    phone: str | None = None
    company_id: str | None = None
    branch_id: str | None = None
    idempotency_key: str | None = None


router = APIRouter(tags=["iam-users"])


def _require_manage_users(context) -> None:
    if context.auth_method == "api_key":
        scopes = context.api_key_scopes or context.permissions or []
        if not scope_allows(scopes, "user.manage"):
            raise HTTPException(status_code=403, detail="API key missing scope: user.manage")
        return
    if "tenant_admin" in {r.lower() for r in context.roles}:
        return
    if not has_permission(context.org_id, context.user_id, "user.manage"):
        raise HTTPException(status_code=403, detail="user.manage permission required")


@router.get("/users", response_model=UserListResponse)
def list_users(
    limit: int = 50,
    offset: int = 0,
    context=Depends(build_request_context),
) -> UserListResponse:
    _require_manage_users(context)
    rows = user_repo.list_users(context.org_id, limit=min(limit, 200), offset=offset)
    items = [
        UserResponse(
            id=row["id"],
            org_id=row["org_id"],
            email=row["email"],
            display_name=row["display_name"],
            status=row["status"],
            mfa_enabled=bool(row.get("mfa_enabled")),
            phone=row.get("phone"),
        )
        for row in rows
    ]
    return UserListResponse(
        request_id=context.request_id,
        items=items,
        total=len(items),
        limit=limit,
        offset=offset,
        confidence=0.99,
        verification_status="iam_users_listed",
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str, context=Depends(build_request_context)) -> UserResponse:
    _require_manage_users(context)
    row = user_repo.get_by_id(context.org_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=row["id"],
        org_id=row["org_id"],
        email=row["email"],
        display_name=row["display_name"],
        status=row["status"],
        mfa_enabled=bool(row.get("mfa_enabled")),
        phone=row.get("phone"),
    )


@router.post("/users")
def create_user(body: CreateUserRequest, context=Depends(build_request_context)) -> dict:
    _require_manage_users(context)
    check_idempotency("iam:user_create", context, body.idempotency_key)
    try:
        validate_password_strength(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    role = role_repo.get_role_by_name(context.org_id, body.role_name)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    user = user_repo.create_user(
        org_id=context.org_id,
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        phone=body.phone,
    )
    user_repo.assign_role(
        org_id=context.org_id,
        user_id=user["id"],
        role_id=role["id"],
        company_id=body.company_id,
        branch_id=body.branch_id,
    )
    emit_user_created(org_id=context.org_id, user_id=user["id"], email=user["email"], trace_id=context.request_id)
    emit_role_assigned(
        org_id=context.org_id,
        user_id=user["id"],
        role_name=body.role_name,
        trace_id=context.request_id,
        company_id=body.company_id,
        branch_id=body.branch_id,
    )
    mark_idempotency("iam:user_create", context, body.idempotency_key)
    return {
        "request_id": context.request_id,
        "user": user,
        "confidence": 0.99,
        "verification_status": "iam_user_created",
    }


@router.post("/users/{user_id}/roles")
def assign_user_role(
    user_id: str,
    body: AssignRoleRequest,
    context=Depends(build_request_context),
) -> dict:
    _require_manage_users(context)
    check_idempotency("iam:role_assign", context, body.idempotency_key)
    role = role_repo.get_role_by_name(context.org_id, body.role_name)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    user_repo.assign_role(
        org_id=context.org_id,
        user_id=user_id,
        role_id=role["id"],
        company_id=body.company_id,
        branch_id=body.branch_id,
    )
    emit_role_assigned(
        org_id=context.org_id,
        user_id=user_id,
        role_name=body.role_name,
        trace_id=context.request_id,
        company_id=body.company_id,
        branch_id=body.branch_id,
    )
    mark_idempotency("iam:role_assign", context, body.idempotency_key)
    return {
        "request_id": context.request_id,
        "status": "assigned",
        "user_id": user_id,
        "role_name": body.role_name,
        "confidence": 0.99,
        "verification_status": "iam_role_assigned",
    }
