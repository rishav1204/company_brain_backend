from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.repositories import organization_repo, permission_repo, role_repo, user_repo
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.middleware.mutation_guard import require_db_mutation
from app.modules.core.iam.validators.org_validator import validate_org_slug
from app.modules.core.iam.validators.permission_validator import validate_permission_key

router = APIRouter(tags=["iam-admin"])


def _require_admin(context) -> None:
    require_db_mutation(
        context,
        ["org.admin"],
        detail="org.admin permission required",
        allow_tenant_admin=True,
    )


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|deactivated)$")
    idempotency_key: str | None = None


class CreateRoleRequest(BaseModel):
    name: str
    description: str | None = None
    policy_context: dict = Field(default_factory=dict)
    idempotency_key: str | None = None


class UpdateRoleRequest(BaseModel):
    description: str | None = None
    policy_context: dict | None = None


class RolePermissionRequest(BaseModel):
    permission_key: str


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: str
    country_code: str = "IN"
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    plan: str = "starter"
    idempotency_key: str | None = None


class UpdateOrgRequest(BaseModel):
    name: str | None = None
    timezone: str | None = None
    currency: str | None = None


class UpdateCompanyRequest(BaseModel):
    legal_name: str | None = None
    gstin: str | None = None
    status: str | None = None


class UpdateBranchRequest(BaseModel):
    branch_name: str | None = None
    state_code: str | None = None


class CreateCompanyRequest(BaseModel):
    legal_name: str
    base_currency: str = "INR"
    financial_year_start: str = "04-01"
    gstin: str | None = None
    idempotency_key: str | None = None


class CreateBranchRequest(BaseModel):
    company_id: str
    branch_code: str
    branch_name: str
    state_code: str | None = None
    idempotency_key: str | None = None


class CreateBusinessUnitRequest(BaseModel):
    unit_code: str
    unit_name: str
    company_id: str | None = None
    idempotency_key: str | None = None


@router.patch("/users/{user_id}")
def update_user_status(user_id: str, body: UpdateUserStatusRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    check_idempotency("iam:user_status", context, body.idempotency_key)
    row = user_repo.update_status(context.org_id, user_id, body.status)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if body.status == "suspended":
        from app.modules.core.iam.repositories import session_repo

        session_repo.revoke_all_for_user(context.org_id, user_id)
    mark_idempotency("iam:user_status", context, body.idempotency_key)
    return {"request_id": context.request_id, "user": row, "verification_status": "iam_user_status_updated"}


@router.post("/admin/users/{user_id}/sessions/revoke-all")
def admin_revoke_all_sessions(user_id: str, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    from app.modules.core.iam.repositories import session_repo
    from app.modules.core.iam.services.auth_audit_service import record_auth_event

    count = session_repo.revoke_all_for_user(context.org_id, user_id)
    record_auth_event(
        event="admin_revoke_sessions",
        success=True,
        org_id=context.org_id,
        user_id=user_id,
        metadata={"revoked_count": count, "actor_id": context.user_id},
    )
    return {
        "request_id": context.request_id,
        "status": "revoked",
        "revoked_count": count,
        "verification_status": "iam_admin_sessions_revoked",
    }


@router.post("/roles")
def create_role(body: CreateRoleRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    check_idempotency("iam:role_create", context, body.idempotency_key)
    existing = role_repo.get_role_by_name(context.org_id, body.name)
    if existing:
        raise HTTPException(status_code=409, detail="Role already exists")
    row = role_repo.create_role(
        context.org_id,
        body.name,
        description=body.description,
        policy_context=body.policy_context,
    )
    mark_idempotency("iam:role_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "role": row, "verification_status": "iam_role_created"}


@router.get("/roles/{role_id}")
def get_role(role_id: str, context=Depends(build_request_context)) -> dict:
    row = role_repo.get_role_by_id(context.org_id, role_id)
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    return {
        "request_id": context.request_id,
        "id": row["id"],
        "org_id": row["org_id"],
        "name": row["name"],
        "description": row.get("description"),
        "system_role": bool(row.get("system_role")),
        "policy_context": row.get("policy_context") or {},
        "verification_status": "iam_role_fetched",
    }


@router.patch("/roles/{role_id}")
def update_role(role_id: str, body: UpdateRoleRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    row = role_repo.update_role(
        context.org_id,
        role_id,
        description=body.description,
        policy_context=body.policy_context,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"request_id": context.request_id, "role": row, "verification_status": "iam_role_updated"}


@router.post("/roles/{role_id}/permissions")
def add_role_permission(role_id: str, body: RolePermissionRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    try:
        validate_permission_key(body.permission_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    perm = permission_repo.get_by_key(body.permission_key)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    role_repo.assign_permission(context.org_id, role_id, perm["id"])
    return {"request_id": context.request_id, "status": "assigned", "verification_status": "iam_role_permission_added"}


@router.delete("/roles/{role_id}/permissions/{permission_key}")
def remove_role_permission(role_id: str, permission_key: str, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    perm = permission_repo.get_by_key(permission_key)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    role_repo.remove_permission(context.org_id, role_id, perm["id"])
    return {"request_id": context.request_id, "status": "removed", "verification_status": "iam_role_permission_removed"}


@router.post("/organizations")
def create_organization(body: CreateOrganizationRequest, context=Depends(build_request_context)) -> dict:
    if "tenant_admin" not in {r.lower() for r in context.roles}:
        raise HTTPException(status_code=403, detail="tenant_admin required to provision organizations")
    try:
        validate_org_slug(body.slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    check_idempotency("iam:org_create", context, body.idempotency_key)
    row = organization_repo.create_organization(
        body.name,
        body.slug,
        country_code=body.country_code,
        timezone=body.timezone,
        currency=body.currency,
        plan=body.plan,
    )
    try:
        from app.modules.platform.billing.services.subscription_service import subscription_service

        plan_key = body.plan or "finance_starter"
        subscription_service.bootstrap_org(str(row["id"]), plan_key=plan_key)
    except Exception:
        pass
    mark_idempotency("iam:org_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "organization": row, "verification_status": "iam_org_created"}


@router.patch("/organizations/current")
def update_current_org(body: UpdateOrgRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    row = organization_repo.update_organization(
        context.org_id,
        name=body.name,
        timezone=body.timezone,
        currency=body.currency,
    )
    return {"request_id": context.request_id, "organization": row, "verification_status": "iam_org_updated"}


@router.post("/organizations/companies")
def create_company(body: CreateCompanyRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    try:
        from app.modules.platform.billing.services.usage_service import usage_service

        usage_service.check_quota(context.org_id, "max_entities", increment=1)
    except Exception as exc:
        from app.modules.platform.billing.exceptions import BillingDenied
        from fastapi import HTTPException

        if isinstance(exc, BillingDenied):
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    check_idempotency("iam:company_create", context, body.idempotency_key)
    row = organization_repo.create_company(
        context.org_id,
        body.legal_name,
        base_currency=body.base_currency,
        financial_year_start=body.financial_year_start,
        gstin=body.gstin,
    )
    mark_idempotency("iam:company_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "company": row, "verification_status": "iam_company_created"}


@router.patch("/organizations/companies/{company_id}")
def update_company(company_id: str, body: UpdateCompanyRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    row = organization_repo.update_company(
        context.org_id,
        company_id,
        legal_name=body.legal_name,
        gstin=body.gstin,
        status=body.status,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"request_id": context.request_id, "company": row, "verification_status": "iam_company_updated"}


@router.post("/organizations/branches")
def create_branch(body: CreateBranchRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    check_idempotency("iam:branch_create", context, body.idempotency_key)
    row = organization_repo.create_branch(
        context.org_id,
        body.company_id,
        body.branch_code,
        body.branch_name,
        state_code=body.state_code,
    )
    mark_idempotency("iam:branch_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "branch": row, "verification_status": "iam_branch_created"}


@router.patch("/organizations/branches/{branch_id}")
def update_branch(branch_id: str, body: UpdateBranchRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    row = organization_repo.update_branch(
        context.org_id,
        branch_id,
        branch_name=body.branch_name,
        state_code=body.state_code,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return {"request_id": context.request_id, "branch": row, "verification_status": "iam_branch_updated"}


@router.get("/organizations/business-units")
def list_business_units(context=Depends(build_request_context)) -> dict:
    rows = organization_repo.list_business_units(context.org_id)
    return {"request_id": context.request_id, "items": rows, "verification_status": "iam_business_units_listed"}


@router.post("/organizations/business-units")
def create_business_unit(body: CreateBusinessUnitRequest, context=Depends(build_request_context)) -> dict:
    _require_admin(context)
    check_idempotency("iam:bu_create", context, body.idempotency_key)
    row = organization_repo.create_business_unit(
        context.org_id,
        body.unit_code,
        body.unit_name,
        company_id=body.company_id,
    )
    mark_idempotency("iam:bu_create", context, body.idempotency_key)
    return {"request_id": context.request_id, "business_unit": row, "verification_status": "iam_business_unit_created"}


@router.get("/organizations/validate-slug/{slug}")
def validate_slug(slug: str, context=Depends(build_request_context)) -> dict:
    try:
        validate_org_slug(slug)
    except ValueError as exc:
        return {"request_id": context.request_id, "valid": False, "reason": str(exc)}
    return {"request_id": context.request_id, "valid": True, "verification_status": "slug_valid"}
