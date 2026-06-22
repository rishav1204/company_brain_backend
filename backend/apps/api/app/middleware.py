from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.services.metrics import metrics_store
from app.services.rate_limiter import rate_limiter
from app.services.trace import trace_span

_PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.api_prefix}/auth/password/login",
    f"{settings.api_prefix}/auth/dev/create-user",
    f"{settings.api_prefix}/auth/oidc/start",
    f"{settings.api_prefix}/auth/oidc/callback",
    f"{settings.api_prefix}/auth/oidc/refresh",
    f"{settings.api_prefix}/auth/login",
    f"{settings.api_prefix}/auth/refresh",
    f"{settings.api_prefix}/auth/invite/accept",
}

_PUBLIC_PATH_PREFIXES = (
    "/integrations/webhooks/inbound/",
)

# Some dev proxies mount at /api/v1 and forward the remainder only (e.g. /auth/password/login).
_PUBLIC_PATH_SUFFIXES = {
    "/auth/password/login",
    "/auth/dev/create-user",
    "/auth/oidc/start",
    "/auth/oidc/callback",
    "/auth/oidc/refresh",
    "/auth/login",
    "/auth/refresh",
    "/auth/invite/accept",
}


def _normalize_path(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def _is_public_path(path: str) -> bool:
    normalized = _normalize_path(path)
    if normalized in _PUBLIC_PATHS or normalized in _PUBLIC_PATH_SUFFIXES:
        return True
    prefixed = f"{settings.api_prefix.rstrip('/')}{normalized}"
    if prefixed in _PUBLIC_PATHS:
        return True
    for prefix in _PUBLIC_PATH_PREFIXES:
        if prefix in normalized or prefix in path:
            return True
    return False


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Always allow CORS preflight to pass through (CORSMiddleware will handle it).
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if _is_public_path(request.url.path):
            return await call_next(request)

        org_id = request.headers.get("x-org-id")
        if not org_id:
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                org_id = "token-org-scope"
        if not org_id:
            metrics_store.incr_request_error()
            return JSONResponse(status_code=401, content={"detail": "Missing authenticated org or bearer token"})

        if org_id != "token-org-scope":
            try:
                from app.modules.platform.billing.exceptions import BillingDenied
                from app.modules.platform.billing.services.usage_service import usage_service

                usage_service.check_quota(org_id, "api_calls_monthly", increment=1)
            except BillingDenied as exc:
                metrics_store.incr_request_error()
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.message, "code": exc.code},
                )

        limit_key = org_id
        decision = rate_limiter.check(limit_key)
        if not decision.allowed:
            metrics_store.incr_request_error()
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(decision.retry_after_seconds),
                    "X-RateLimit-Remaining": "0",
                },
            )

        metrics_store.incr_request()
        try:
            with trace_span("http.request", path=request.url.path, method=request.method, org_hint=org_id):
                response: Response = await call_next(request)
            if response.status_code >= 400:
                metrics_store.incr_request_error()
            elif org_id and org_id != "token-org-scope":
                try:
                    from app.modules.platform.billing.services.usage_service import usage_service

                    usage_service.record(org_id, "api_calls")
                except Exception:
                    pass
            response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
            return response
        except Exception:
            metrics_store.incr_request_error()
            raise
