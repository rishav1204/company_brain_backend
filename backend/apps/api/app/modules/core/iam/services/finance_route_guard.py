"""API key scope enforcement for Finance OS routes."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.request_context import RequestContext
from app.modules.core.iam.services.api_key_auth_service import scope_allows
from app.modules.core.iam.services.rbac_service import permission_key_for_action

_READ_SCOPES = frozenset({"read", "list", "get"})


def resolve_required_scope(
    *,
    action: str | None = None,
    object_type: str = "workflow",
    mode: str = "read",
) -> str:
    if action:
        key = permission_key_for_action(action, object_type)
        if key:
            return key
        if "." in action:
            return action
        return f"{object_type}.{action}"
    if mode in _READ_SCOPES:
        return f"{object_type}.read"
    return f"{object_type}.write"


def enforce_finance_route_access(
    context: RequestContext,
    *,
    action: str | None = None,
    object_type: str = "workflow",
    mode: str = "read",
    required_scope: str | None = None,
) -> None:
    """Enforce API key scopes on Finance OS handlers. JWT/header auth is unchanged."""
    if context.auth_method != "api_key":
        return
    scopes = context.api_key_scopes or context.permissions or []
    primary = required_scope or resolve_required_scope(action=action, object_type=object_type, mode=mode)
    fallbacks = [primary, f"{object_type}.read", f"{object_type}.write", "workflow.read", "workflow.write", "admin"]
    if any(scope_allows(scopes, candidate) for candidate in fallbacks):
        return
    raise HTTPException(status_code=403, detail=f"API key missing scope (required one of: {', '.join(fallbacks)})")
