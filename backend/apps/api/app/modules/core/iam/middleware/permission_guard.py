"""FastAPI dependency helpers for IAM permission checks (used alongside global middleware)."""

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.rbac_service import has_permission, list_role_names
from app.services.object_context import ObjectContext

_FINANCIAL_PREFIXES = ("erp.", "ap.", "ar.", "payment.", "journal.", "gst.", "tds.", "gl.", "voucher.", "fiscal.")

# Explicit non-financial permissions tenant_admin may hold without per-key grants (SEC-17).
_TENANT_ADMIN_ALLOWED = frozenset({
    "org.read",
    "org.settings.read",
    "audit.read",
    "iam.user.read",
    "iam.role.read",
    "iam.permission.read",
})


def _is_financial_permission(permission_key: str) -> bool:
    lowered = permission_key.lower()
    return any(lowered.startswith(p) for p in _FINANCIAL_PREFIXES)


def require_permission(permission_key: str):
    def _guard(context=Depends(build_request_context)):
        if has_permission(context.org_id, context.user_id, permission_key):
            return context
        if not _is_financial_permission(permission_key):
            if permission_key in _TENANT_ADMIN_ALLOWED:
                db_roles = {r.lower() for r in list_role_names(context.org_id, context.user_id)}
                if "tenant_admin" in db_roles:
                    return context
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")

    return _guard


def workflow_permission_guard(
    permission_key: str,
    *,
    object_type: str = "workflow",
    action: str | None = None,
):
    def _guard(context=Depends(build_request_context)):
        from app.modules.core.iam.middleware.mutation_guard import db_roles_for_user, require_db_mutation
        from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access

        enforce_finance_route_access(
            context,
            action=action,
            object_type=object_type,
            mode="read",
            required_scope=permission_key,
        )
        if context.auth_method == "api_key":
            return context
        require_db_mutation(
            context,
            [permission_key],
            detail=f"Missing permission: {permission_key}",
            allow_tenant_admin=True,
        )
        object_context = ObjectContext(object_type=object_type, object_id="workflow")
        decision = evaluate_access(
            org_id=context.org_id,
            user_id=context.user_id,
            roles=db_roles_for_user(context.org_id, context.user_id),
            action=action or permission_key,
            object_context=object_context,
            attrs=context.attrs,
        )
        if decision.allowed:
            return context
        raise HTTPException(status_code=403, detail=decision.reason or f"Missing permission: {permission_key}")

    return _guard
