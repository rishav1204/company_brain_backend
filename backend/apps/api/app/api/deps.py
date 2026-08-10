from fastapi import Header, HTTPException, Request
from jwt import InvalidTokenError

from app.core.config import settings
from app.core.request_context import RequestContext, set_request_context
from app.modules.core.iam.services.api_key_auth_service import authenticate_api_key, scope_allows
from app.modules.platform.integrations.services.integration_api_key_auth import authenticate_integration_api_key
from app.modules.platform.integrations.services.rate_limit_service import integrations_rate_limit_service
from app.services.jwt_auth import decode_bearer_token


def _trace_from_request(request: Request | None) -> tuple[str | None, str | None, str | None]:
    if request is None:
        return None, None, None
    trace_id = getattr(request.state, "trace_id", None) or request.headers.get("x-trace-id")
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    ip_address = getattr(request.state, "client_ip", None) or (request.client.host if request.client else None)
    user_agent = getattr(request.state, "user_agent", None) or request.headers.get("user-agent")
    return trace_id, request_id, ip_address, user_agent


def _authorization_from_request(request: Request, authorization: str | None = None) -> str | None:
    """Resolve bearer auth from header or HttpOnly cookie. SSE uses X-SSE-Token via separate path."""
    if authorization and authorization.strip():
        return authorization.strip()
    header = request.headers.get("authorization")
    if header and header.strip():
        return header.strip()
    cookie_token = request.cookies.get("cb_access_token") or request.cookies.get("access_token")
    if cookie_token and str(cookie_token).strip():
        return f"Bearer {str(cookie_token).strip()}"
    return None


def _is_sse_stream_path(path: str) -> bool:
    normalized = path.rstrip("/")
    return "/realtime/" in normalized or normalized.endswith("/events/stream")


def _sse_bearer_from_header(request: Request) -> str | None:
    """SEC-03: short-lived SSE token instead of query-string JWT."""
    from app.core.sse_token_service import consume_sse_token

    raw = request.headers.get("x-sse-token") or request.headers.get("X-SSE-Token")
    if not raw or not str(raw).strip():
        return None
    info = consume_sse_token(str(raw).strip())
    if not info:
        return None
    from app.modules.core.iam.services.jwt_service import issue_access_token
    from app.modules.core.iam.repositories import permission_repo, role_repo
    from app.modules.core.iam.services.rbac_service import list_role_names, merge_policy_context_from_rows

    org_id = info["org_id"]
    user_id = info["user_id"]
    roles = list_role_names(org_id, user_id)
    permissions = permission_repo.list_permissions_for_user(org_id, user_id)
    role_rows = role_repo.list_user_roles(org_id, user_id)
    attrs = merge_policy_context_from_rows(role_rows)
    token = issue_access_token(
        org_id=org_id,
        user_id=user_id,
        roles=roles,
        permissions=permissions,
        attrs=attrs,
        session_id=info.get("session_id"),
    )
    return f"Bearer {token}"


def build_request_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_org_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_roles: str | None = Header(default=None),
) -> RequestContext:
    trace_id, header_request_id, ip_address, user_agent = _trace_from_request(request)
    authorization = _authorization_from_request(request, authorization)
    if not authorization and _is_sse_stream_path(request.url.path):
        authorization = _sse_bearer_from_header(request)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token.startswith("cb_"):
            api_auth = authenticate_api_key(token)
            if not api_auth:
                raise HTTPException(status_code=401, detail="Invalid API key")
            ctx = set_request_context(
                org_id=api_auth["org_id"],
                user_id=api_auth["user_id"],
                roles=api_auth["roles"],
                permissions=api_auth["scopes"],
                auth_method="api_key",
                api_key_id=api_auth["api_key_id"],
                api_key_scopes=api_auth["scopes"],
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
                attrs={"actor_type": "api_key", "api_key_id": api_auth["api_key_id"]},
            )
            if header_request_id:
                ctx.request_id = header_request_id
            return ctx
        if token.startswith("cbk_"):
            api_auth = authenticate_integration_api_key(token)
            if not api_auth:
                raise HTTPException(status_code=401, detail="Invalid integration API key")
            if not integrations_rate_limit_service.allow_api_key(
                org_id=str(api_auth["org_id"]), api_key_id=str(api_auth["api_key_id"])
            ):
                raise HTTPException(status_code=429, detail="Integration API key rate limit exceeded")
            ctx = set_request_context(
                org_id=api_auth["org_id"],
                user_id=api_auth["user_id"],
                roles=api_auth["roles"],
                permissions=api_auth["scopes"],
                auth_method="api_key",
                api_key_id=api_auth["api_key_id"],
                api_key_scopes=api_auth["scopes"],
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
                attrs={"actor_type": "api_key", "api_key_id": api_auth["api_key_id"]},
            )
            if header_request_id:
                ctx.request_id = header_request_id
            return ctx
        try:
            principal = decode_bearer_token(token)
        except InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid bearer token: {exc}") from exc
        if not principal.roles:
            raise HTTPException(status_code=403, detail="No roles available for access control")
        ctx = set_request_context(
            org_id=principal.org_id,
            user_id=principal.user_id,
            roles=principal.roles,
            source_acl=principal.source_acl,
            attrs=principal.attrs,
            permissions=principal.permissions,
            session_id=principal.session_id,
            auth_method="jwt",
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if header_request_id:
            ctx.request_id = header_request_id
        return ctx

    if settings.auth_mode == "bearer_only":
        raise HTTPException(status_code=401, detail="Bearer token required")

    if not x_org_id or not x_user_id:
        raise HTTPException(status_code=401, detail="Missing authenticated context headers or bearer token")

    roles = [role.strip() for role in (x_roles or "").split(",") if role.strip()]
    if not roles:
        raise HTTPException(status_code=403, detail="No roles available for access control")
    ctx = set_request_context(
        org_id=x_org_id,
        user_id=x_user_id,
        roles=roles,
        source_acl=[],
        attrs={},
        auth_method="header",
        trace_id=trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if header_request_id:
        ctx.request_id = header_request_id
    return ctx


def require_api_scope(required_scope: str):
    from fastapi import Depends as FastAPIDepends

    def _guard(context: RequestContext = FastAPIDepends(build_request_context)) -> RequestContext:
        if context.auth_method == "api_key":
            scopes = context.api_key_scopes or context.permissions or []
            if not scope_allows(scopes, required_scope):
                raise HTTPException(status_code=403, detail=f"API key missing scope: {required_scope}")
        return context

    return _guard
