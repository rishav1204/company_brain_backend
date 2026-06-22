from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.modules.platform.integrations.repositories.api_key_repository import api_key_repository
from app.modules.platform.api_gateway.services.rate_limit_service import gateway_rate_limit_service


class GatewayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer cbk_"):
            return await call_next(request)

        token = auth.split(" ", 1)[1].strip()
        from hashlib import sha256

        key_hash = sha256(token.encode()).hexdigest()
        record = api_key_repository.get_by_hash(key_hash)
        if not record:
            return await call_next(request)

        org_id = str(record.get("org_id") or "")
        api_key_id = str(record.get("id") or "")
        allowlist = record.get("ip_allowlist") or []
        if allowlist:
            client_ip = request.client.host if request.client else None
            if client_ip and client_ip not in allowlist:
                return JSONResponse(status_code=403, content={"detail": "IP not in allowlist"})

        per_min = int(record.get("rate_limit_per_minute") or 100)
        per_hr = int(record.get("rate_limit_per_hour") or 1000)
        if not gateway_rate_limit_service.allow(
            org_id=org_id,
            api_key_id=api_key_id,
            per_minute=per_min,
            per_hour=per_hr,
        ):
            return JSONResponse(status_code=429, content={"detail": "API key rate limit exceeded"})

        return await call_next(request)
