"""DB-backed permission checks for IAM/workflow mutations (SEC-16)."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.request_context import RequestContext
from app.modules.core.iam.services.api_key_auth_service import scope_allows
from app.modules.core.iam.services.rbac_service import has_permission, list_role_names

_FINANCE_ADMIN_ROLE_FRAGMENTS = ("finance_admin", "ap_manager", "ar_manager", "gl_manager", "gl_admin")


def db_roles_for_user(org_id: str, user_id: str) -> list[str]:
    return list_role_names(org_id, user_id)


def db_has_role(org_id: str, user_id: str, role_name: str) -> bool:
    target = str(role_name or "").lower()
    return target in {r.lower() for r in db_roles_for_user(org_id, user_id)}


def db_finance_admin(org_id: str, user_id: str) -> bool:
    roles = {r.lower() for r in db_roles_for_user(org_id, user_id)}
    if "tenant_admin" in roles:
        return False
    return any(any(frag in r for frag in _FINANCE_ADMIN_ROLE_FRAGMENTS) for r in roles)


def require_db_mutation(
    context: RequestContext,
    permission_keys: list[str],
    *,
    detail: str = "Insufficient permission for mutation",
    allow_tenant_admin: bool = False,
    allow_finance_admin_role: bool = False,
    api_key_scopes: list[str] | None = None,
) -> None:
    """Verify mutation permission from database — never trust stale JWT role claims."""
    if context.auth_method == "api_key":
        scopes = [s.lower() for s in (api_key_scopes or context.api_key_scopes or context.permissions or [])]
        for key in permission_keys:
            if key.lower() in scopes or scope_allows(scopes, key):
                return
        raise HTTPException(status_code=403, detail=detail)

    for key in permission_keys:
        if key and has_permission(context.org_id, context.user_id, key):
            return
    if allow_tenant_admin and db_has_role(context.org_id, context.user_id, "tenant_admin"):
        return
    if allow_finance_admin_role and db_finance_admin(context.org_id, context.user_id):
        return
    raise HTTPException(status_code=403, detail=detail)
