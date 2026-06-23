"""FastAPI dependency helpers for IAM permission checks (used alongside global middleware)."""

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.rbac_service import has_permission, list_role_names


def require_permission(permission_key: str):
    def _guard(context=Depends(build_request_context)):
        if has_permission(context.org_id, context.user_id, permission_key):
            return context
        db_roles = {r.lower() for r in list_role_names(context.org_id, context.user_id)}
        if "tenant_admin" in db_roles:
            return context
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")

    return _guard
