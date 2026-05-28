from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.modules.platform.governance.services.policy_service import governance_policy_service
from app.services.logger import log_event


class GovernanceEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Optional header-based governance pre-check.
    X-Governance-Action + X-Governance-Attrs (JSON) for simulation endpoints.
    """

    async def dispatch(self, request: Request, call_next):
        action = request.headers.get("x-governance-action")
        if not action or request.method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)
        org_id = request.headers.get("x-org-id")
        user_id = request.headers.get("x-user-id")
        roles_header = request.headers.get("x-roles", "")
        if not org_id or not user_id:
            return await call_next(request)
        roles = [r.strip() for r in roles_header.split(",") if r.strip()]
        created_by = request.headers.get("x-created-by") or request.headers.get("x-governance-creator")
        try:
            result = governance_policy_service.evaluate(
                org_id,
                action=action,
                attrs={},
                roles=roles,
                created_by=created_by,
                actor_user_id=user_id,
            )
            if not result.allowed:
                log_event("governance.middleware.blocked", org_id=org_id, action=action)
                return JSONResponse(status_code=403, content={"detail": result.reason, "violations": result.violations})
        except Exception as exc:
            log_event("governance.middleware.error", error=str(exc))
        return await call_next(request)
