"""FastAPI dependency helpers for workflow module routes — ABAC-aware."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.services.object_context import ObjectContext


def require_workflow_permission(
    permission_key: str,
    *,
    object_type: str = "workflow",
    mode: str = "read",
    action: str | None = None,
):
    effective_action = action or permission_key

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
        decision = evaluate_access(
            org_id=context.org_id,
            user_id=context.user_id,
            roles=context.roles,
            action=effective_action,
            object_context=ObjectContext(object_type=object_type, object_id="workflow"),
            attrs=context.attrs,
        )
        if decision.allowed:
            return context
        if "tenant_admin" in {r.lower() for r in (context.roles or [])}:
            return context
        raise HTTPException(status_code=403, detail=decision.reason or f"Missing permission: {permission_key}")

    return _guard
