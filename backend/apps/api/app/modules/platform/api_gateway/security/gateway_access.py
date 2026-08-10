from __future__ import annotations

from fastapi import HTTPException

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.platform.api_gateway.schemas.scope_catalog import scope_to_action
from app.modules.platform.billing.security.billing_enforce import enforce_billing
from app.services.object_context import ObjectContext

_FORBIDDEN_KEY_SCOPES = frozenset({"*", "admin"})


def _scope_allows(context, required_scopes: list[str]) -> bool:
    if not required_scopes:
        return True
    key_scopes = {str(s).strip() for s in (context.api_key_scopes or context.permissions or []) if str(s).strip()}
    if key_scopes & _FORBIDDEN_KEY_SCOPES:
        return False
    explicit_required = [s for s in required_scopes if s not in _FORBIDDEN_KEY_SCOPES]
    if not explicit_required:
        return False
    return any(s in key_scopes for s in explicit_required)


def enforce_gateway_action(
    context,
    *,
    action: str,
    required_scopes: list[str] | None = None,
    object_type: str = "api_gateway",
    object_id: str = "gateway",
) -> None:
    enforce_billing(context.org_id, "api_platform")
    if context.auth_method == "api_key" and required_scopes and not _scope_allows(context, required_scopes):
        raise HTTPException(status_code=403, detail="API key scope violation")

    attrs = dict(context.attrs or {})
    if context.auth_method == "api_key":
        attrs["actor_type"] = "api_key"
        if context.api_key_id:
            attrs["api_key_id"] = context.api_key_id

    policy_action = scope_to_action(action) if "." not in action else action
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action=policy_action,
        object_context=ObjectContext(object_type=object_type, object_id=object_id),
        attrs=attrs,
        actor_type=attrs.get("actor_type"),
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason or "Access denied")
