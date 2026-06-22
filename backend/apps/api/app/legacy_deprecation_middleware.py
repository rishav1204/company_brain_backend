from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

# Legacy v1 routes scheduled for removal. Modular successors live under modules/.
_LEGACY_ROUTE_SUCCESSORS: dict[str, str] = {
    "/agents/run": "/finance-os/agents/run",
    "/agents/runs": "/finance-os/agents/executions",
    "/graph/bootstrap": "/finance-os/graph/bootstrap",
    "/graph/extract": "/finance-os/graph/extract",
    "/graph/queries": "/finance-os/graph/queries",
    "/decisions": "/finance-os/memory",
    "/memory": "/finance-os/memory",
    "/memory/decay/run": "/finance-os/memory/admin/decay/run",
    "/workflows": "/workflows/definitions",
    "/auth/password/login": "/auth/login",
}

# Longest-prefix wins when matching nested legacy paths.
_LEGACY_PREFIX_SUCCESSORS: tuple[tuple[str, str], ...] = (
    ("/agents/", "/finance-os/agents/"),
    ("/graph/", "/finance-os/graph/"),
)

_SUNSET = "Wed, 31 Dec 2026 23:59:59 GMT"


def _resolve_successor(relative: str) -> str | None:
    key = relative.rstrip("/") or "/"
    exact = _LEGACY_ROUTE_SUCCESSORS.get(key)
    if exact:
        return exact
    if key.startswith("/workflows/"):
        if key.endswith("/actions"):
            return "/approvals"
        if key.endswith("/timeline"):
            return "/workflows/instances"
        return None
    for prefix, successor in _LEGACY_PREFIX_SUCCESSORS:
        if relative.startswith(prefix):
            return successor
    return None


class LegacyDeprecationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        if not path.startswith(settings.api_prefix):
            return response
        relative = path[len(settings.api_prefix) :] or "/"
        successor = _resolve_successor(relative)
        if successor is None:
            return response
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = _SUNSET
        response.headers["Link"] = f'<{settings.api_prefix}{successor}>; rel="successor-version"'
        return response
