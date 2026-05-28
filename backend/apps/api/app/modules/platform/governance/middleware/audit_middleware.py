from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.utils.audit_context import should_skip_auto_audit
from app.services.logger import log_event

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_SKIP_PREFIXES = (
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.api_prefix}/audit/logs",
    f"{settings.api_prefix}/audit/export",
)


def _resolve_actor(request: Request) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Resolve org/user/trace from request context (JWT) or headers."""
    trace_id = getattr(request.state, "trace_id", None)
    request_id = getattr(request.state, "request_id", None)
    ip_address = getattr(request.state, "client_ip", None)
    user_agent = getattr(request.state, "user_agent", None)
    try:
        from app.core.request_context import get_request_context

        ctx = get_request_context()
        return ctx.org_id, ctx.user_id, ctx.trace_id or trace_id, ctx.request_id or request_id, user_agent
    except RuntimeError:
        pass
    org_id = request.headers.get("x-org-id")
    user_id = request.headers.get("x-user-id")
    return org_id, user_id, trace_id, request_id, user_agent


class AuditCaptureMiddleware(BaseHTTPMiddleware):
    """Auto-audit mutating API calls (JWT + header auth). Skips when audit_service already logged."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method not in _MUTATING:
            return response
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response
        if should_skip_auto_audit():
            return response
        org_id, user_id, trace_id, request_id, user_agent = _resolve_actor(request)
        ip_address = getattr(request.state, "client_ip", None)
        if not org_id or not user_id:
            return response
        if response.status_code >= 500:
            return response
        try:
            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=user_id,
                action=f"http.{request.method.lower()}.{path.rstrip('/').split('/')[-1] or 'root'}",
                object_ref=f"http:{request.method}:{path}",
                payload={"status_code": response.status_code, "method": request.method, "path": path},
                request_id=request_id,
                trace_id=trace_id,
                ip_address=ip_address,
                user_agent=user_agent,
                source_service="governance.audit_middleware",
                skip_auto_audit_flag=True,
            )
        except Exception as exc:
            log_event("governance.audit_middleware.error", error=str(exc))
        return response
