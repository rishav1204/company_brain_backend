"""FastAPI dependency helpers for workflow module routes — ABAC-aware with DB mutation checks (SEC-16)."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.middleware.mutation_guard import db_roles_for_user, require_db_mutation
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
        if mode == "write":
            require_db_mutation(
                context,
                [permission_key],
                detail=f"Missing permission: {permission_key}",
                allow_tenant_admin=True,
            )
        if context.auth_method == "api_key":
            return context
        db_roles = db_roles_for_user(context.org_id, context.user_id)
        decision = evaluate_access(
            org_id=context.org_id,
            user_id=context.user_id,
            roles=db_roles,
            action=effective_action,
            object_context=ObjectContext(object_type=object_type, object_id="workflow"),
            attrs=context.attrs,
        )
        if decision.allowed:
            return context
        raise HTTPException(status_code=403, detail=decision.reason or f"Missing permission: {permission_key}")

    return _guard
