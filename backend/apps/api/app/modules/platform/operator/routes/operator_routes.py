"""Platform operator (SaaS owner) control plane.

Gated by require_permission("platform.admin"), which has no tenant_admin
fallback in permission_guard, so only a principal holding the permission itself
gets in — a customer-company admin cannot reach these paths.
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.platform.operator.schemas.operator_schema import (
    OperatorListResponse,
    SessionRevokeResponse,
    UsageResponse,
    UserStatusRequest,
    UserStatusResponse,
)
from app.modules.platform.operator.services.operator_service import (
    OperatorError,
    UserNotFound,
    operator_service,
)

router = APIRouter(tags=["platform-operator"])

_PLATFORM_ADMIN = require_permission("platform.admin")


@router.get("/ops/platform/orgs", response_model=OperatorListResponse)
def list_orgs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context=Depends(_PLATFORM_ADMIN),
) -> OperatorListResponse:
    """Every tenant org with its plan, status and user counts."""
    result = operator_service.list_organizations(limit=limit, offset=offset)
    return OperatorListResponse(
        request_id=context.request_id,
        verification_status="platform_orgs_listed",
        **result,
    )


@router.get("/ops/platform/users", response_model=OperatorListResponse)
def list_users(
    org_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context=Depends(_PLATFORM_ADMIN),
) -> OperatorListResponse:
    """Users across all orgs, with roles and live session counts."""
    result = operator_service.list_users(
        org_id=org_id, status=status, search=search, limit=limit, offset=offset
    )
    return OperatorListResponse(
        request_id=context.request_id,
        verification_status="platform_users_listed",
        **result,
    )


@router.get("/ops/platform/usage", response_model=UsageResponse)
def usage_by_org(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    context=Depends(_PLATFORM_ADMIN),
) -> UsageResponse:
    """Per-org rollup: AI spend, API calls and billing usage metrics."""
    result = operator_service.usage_by_org(days=days, limit=limit)
    return UsageResponse(
        request_id=context.request_id,
        verification_status="platform_usage_rolled_up",
        **result,
    )


@router.post("/ops/platform/users/{user_id}/status", response_model=UserStatusResponse)
def set_user_status(
    user_id: str,
    body: UserStatusRequest,
    context=Depends(_PLATFORM_ADMIN),
) -> UserStatusResponse:
    """Block (suspended/deactivated) or restore a user in any org. Blocking also
    revokes their live sessions, so access stops immediately rather than at token
    expiry."""
    try:
        result = operator_service.set_user_status(
            user_id=user_id,
            status=body.status,
            actor_user_id=context.user_id,
            actor_org_id=context.org_id,
        )
    except UserNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserStatusResponse(
        request_id=context.request_id,
        verification_status="platform_user_status_updated",
        **result,
    )


@router.post("/ops/platform/users/{user_id}/sessions/revoke-all", response_model=SessionRevokeResponse)
def revoke_all_sessions(user_id: str, context=Depends(_PLATFORM_ADMIN)) -> SessionRevokeResponse:
    """Force logout in any org without changing the user's status."""
    try:
        result = operator_service.revoke_all_sessions(
            user_id=user_id,
            actor_user_id=context.user_id,
            actor_org_id=context.org_id,
        )
    except UserNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionRevokeResponse(
        request_id=context.request_id,
        verification_status="platform_sessions_revoked",
        **result,
    )
