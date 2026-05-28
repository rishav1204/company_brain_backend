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


def build_request_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_org_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_roles: str | None = Header(default=None),
) -> RequestContext:
    trace_id, header_request_id, ip_address, user_agent = _trace_from_request(request)
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
