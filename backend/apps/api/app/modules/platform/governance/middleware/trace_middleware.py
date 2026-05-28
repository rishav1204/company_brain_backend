from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class GovernanceTraceMiddleware(BaseHTTPMiddleware):
    """Inject trace_id / request_id into request state for downstream audit + queues."""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or str(uuid4())
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.trace_id = trace_id
        request.state.request_id = request_id
        request.state.client_ip = request.client.host if request.client else None
        request.state.user_agent = request.headers.get("user-agent")
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Request-Id"] = request_id
        return response
