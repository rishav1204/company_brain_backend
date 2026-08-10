"""ERP permission checks with mandatory DB validation for mutations (SEC-16/SEC-18/SEC-19)."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.request_context import RequestContext
from app.modules.core.iam.middleware.mutation_guard import require_db_mutation
from app.modules.core.iam.services.rbac_service import has_permission


def list_role_names(user: dict | None) -> list[str]:
    """Compatibility shim for tests and callers expecting a role-name helper."""
    if not isinstance(user, dict):
        return []
    roles = user.get("roles") or []
    return [str(r) for r in roles if r]


def _db_has_any_permission(org_id: str, user_id: str, keys: list[str]) -> bool:
    for key in keys:
        if key and has_permission(org_id, user_id, key):
            return True
    return False


def require_erp_mutation_access(
    context: RequestContext,
    *,
    permission_keys: list[str],
    detail: str = "Insufficient permission for ERP mutation",
    allow_finance_admin_role: bool = True,
) -> None:
    """Always verify permissions from database — never trust JWT wildcard or stale claims."""
    require_db_mutation(
        context,
        permission_keys,
        detail=detail,
        allow_finance_admin_role=allow_finance_admin_role,
    )


def require_mutation_access(
    context: RequestContext,
    *,
    permission_keys: list[str],
    detail: str = "Insufficient permission for mutation",
    allow_tenant_admin: bool = False,
) -> None:
    """DB permission re-check for non-ERP mutations (SEC-16)."""
    require_db_mutation(
        context,
        permission_keys,
        detail=detail,
        allow_tenant_admin=allow_tenant_admin,
        allow_finance_admin_role=False,
    )


def require_erp_read_access(
    context: RequestContext,
    *,
    permission_keys: list[str],
    detail: str = "Insufficient permission for ERP read",
) -> None:
    """Read paths: DB check first; JWT permissions only if DB miss and no wildcard."""
    if _db_has_any_permission(context.org_id, context.user_id, permission_keys):
        return
    jwt_perms = [p.lower() for p in (context.permissions or []) if p and p != "*"]
    for key in permission_keys:
        if key.lower() in jwt_perms:
            return
    roles = [r.lower() for r in (context.roles or [])]
    if any("finance" in r for r in roles):
        return
    raise HTTPException(status_code=403, detail=detail)
