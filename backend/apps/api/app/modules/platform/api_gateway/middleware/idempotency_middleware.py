from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.modules.platform.events.services.idempotency_service import platform_idempotency_service


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)

        idem_key = request.headers.get("idempotency-key") or request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        org_id = request.headers.get("x-org-id") or "unknown"
        replay, cached = platform_idempotency_service.check_and_store(
            org_id,
            "api_gateway",
            idem_key,
            request_payload={"method": request.method, "path": request.url.path},
        )
        if replay and cached:
            return JSONResponse(status_code=200, content=cached)

        request.state.idempotency_key = idem_key  # noqa: SLF001
        return await call_next(request)
