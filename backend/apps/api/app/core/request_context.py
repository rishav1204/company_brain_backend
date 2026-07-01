from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class RequestContext:
    request_id: str
    org_id: str
    user_id: str
    roles: list[str]
    trace_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    source_acl: list[str] | None = None
    attrs: dict | None = None
    permissions: list[str] | None = None
    session_id: str | None = None
    auth_method: str = "jwt"
    api_key_id: str | None = None
    api_key_scopes: list[str] | None = None

    @property
    def user(self) -> "RequestContext":
        # Backwards-compat: some guards/routes expect `context.user`.
        return self


_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(
    org_id: str,
    user_id: str,
    roles: list[str],
    source_acl: list[str] | None = None,
    attrs: dict | None = None,
    permissions: list[str] | None = None,
    session_id: str | None = None,
    auth_method: str = "jwt",
    api_key_id: str | None = None,
    api_key_scopes: list[str] | None = None,
    trace_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RequestContext:
    rid = str(uuid4())
    context = RequestContext(
        request_id=rid,
        org_id=org_id,
        user_id=user_id,
        roles=roles,
        trace_id=trace_id or rid,
        ip_address=ip_address,
        user_agent=user_agent,
        source_acl=source_acl or [],
        attrs=attrs or {},
        permissions=permissions or [],
        session_id=session_id,
        auth_method=auth_method,
        api_key_id=api_key_id,
        api_key_scopes=api_key_scopes or [],
    )
    _context.set(context)
    return context


def get_request_context() -> RequestContext:
    current = _context.get()
    if current is None:
        raise RuntimeError("Request context has not been initialized")
    return current
