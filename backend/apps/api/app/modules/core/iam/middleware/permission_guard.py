"""FastAPI dependency helpers for IAM permission checks (used alongside global middleware)."""

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.rbac_service import has_permission


def require_permission(permission_key: str):
    def _guard(context=Depends(build_request_context)):
        if not has_permission(context.org_id, context.user_id, permission_key):
            elevated = "tenant_admin" in {r.lower() for r in context.roles}
            if not elevated:
                raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")
        return context

    return _guard
