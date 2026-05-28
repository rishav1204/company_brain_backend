"""JWT + API-key permission enforcement for workflow module routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.modules.core.iam.services.rbac_service import has_permission


def require_workflow_permission(
    permission_key: str,
    *,
    object_type: str = "workflow",
    mode: str = "read",
    action: str | None = None,
):
    def _guard(context=Depends(build_request_context)):
        enforce_finance_route_access(
            context,
            action=action,
            object_type=object_type,
            mode=mode,
            required_scope=permission_key,
        )
        if context.auth_method == "api_key":
            return context
        if not has_permission(context.org_id, context.user_id, permission_key):
            elevated = "tenant_admin" in {r.lower() for r in (context.roles or [])}
            if not elevated:
                raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")
        return context

    return _guard
