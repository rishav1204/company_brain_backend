from app.core.request_context import RequestContext

SYSTEM_WORKER_ROLES = ["system_worker"]


def build_principal(
    user_id: str,
    roles: list[str],
    attrs: dict | None = None,
    source_acl: list[str] | None = None,
    human_approved: bool = False,
) -> dict:
    return {
        "user_id": user_id,
        "roles": [str(role) for role in roles if str(role).strip()],
        "attrs": attrs if isinstance(attrs, dict) else {},
        "source_acl": [str(item) for item in (source_acl or []) if str(item).strip()],
        "human_approved": bool(human_approved),
    }


def principal_from_request_context(context: RequestContext, human_approved: bool = False) -> dict:
    return build_principal(
        user_id=context.user_id,
        roles=context.roles,
        attrs=context.attrs,
        source_acl=context.source_acl,
        human_approved=human_approved,
    )


def principal_from_envelope(envelope: dict) -> dict:
    root = envelope.get("principal")
    if isinstance(root, dict) and root.get("roles"):
        return _normalize_principal(root)
    payload = envelope.get("payload", {})
    nested = payload.get("principal", {}) if isinstance(payload, dict) else {}
    if isinstance(nested, dict) and nested.get("roles"):
        return _normalize_principal(nested)
    return build_principal(user_id="system-worker", roles=SYSTEM_WORKER_ROLES, attrs={}, human_approved=False)


def _normalize_principal(raw: dict) -> dict:
    roles = raw.get("roles", SYSTEM_WORKER_ROLES)
    if not isinstance(roles, list):
        roles = [str(roles)]
    attrs = raw.get("attrs", {})
    if not isinstance(attrs, dict):
        attrs = {}
    source_acl = raw.get("source_acl", [])
    if not isinstance(source_acl, list):
        source_acl = [str(source_acl)]
    user_id = str(raw.get("user_id", "event-consumer")).strip() or "event-consumer"
    return build_principal(
        user_id=user_id,
        roles=[str(role) for role in roles if str(role).strip()] or SYSTEM_WORKER_ROLES,
        attrs=attrs,
        source_acl=source_acl,
        human_approved=bool(raw.get("human_approved", False)),
    )


def principal_tuple(envelope: dict) -> tuple[list[str], dict, bool, str]:
    principal = principal_from_envelope(envelope)
    return (
        principal["roles"],
        principal["attrs"],
        bool(principal.get("human_approved", False)),
        str(principal.get("user_id", "event-consumer")),
    )
