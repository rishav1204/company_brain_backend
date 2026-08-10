from __future__ import annotations



from starlette.middleware.base import BaseHTTPMiddleware

from starlette.requests import Request

from starlette.responses import JSONResponse, Response



from app.core.config import settings

from app.modules.platform.events.services.idempotency_service import platform_idempotency_service





def _resolve_org_id(request: Request) -> str:

    authorization = request.headers.get("authorization", "")

    if authorization.lower().startswith("bearer "):

        token = authorization.split(" ", 1)[1].strip()

        if not token.startswith(("cb_", "cbk_")):

            try:

                from app.services.jwt_auth import decode_bearer_token



                return decode_bearer_token(token).org_id

            except Exception:

                pass

    cookie_token = request.cookies.get("cb_access_token")

    if cookie_token:

        try:

            from app.services.jwt_auth import decode_bearer_token



            return decode_bearer_token(str(cookie_token).strip()).org_id

        except Exception:

            pass

    org_header = request.headers.get("x-org-id")

    if org_header and str(org_header).strip():

        if settings.app_env.lower() == "prod":

            return "unknown"

        return str(org_header).strip()

    return "unknown"





class IdempotencyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:

        if request.method not in {"POST", "PUT", "PATCH"}:

            return await call_next(request)



        idem_key = request.headers.get("idempotency-key") or request.headers.get("Idempotency-Key")

        if not idem_key:

            return await call_next(request)



        org_id = _resolve_org_id(request)

        if org_id == "unknown":

            return JSONResponse(status_code=401, content={"detail": "Authenticated org required for idempotency"})



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

