from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.services.api_key_auth_service import scope_allows
from app.modules.core.iam.events.role_events import emit_session_revoked
from app.modules.core.iam.repositories import session_repo
from app.modules.core.iam.services.rbac_service import has_permission

router = APIRouter(tags=["iam-sessions"])


class RevokeSessionRequest(BaseModel):
    idempotency_key: str | None = None


def _require_session_perm(context, perm: str) -> None:
    if context.auth_method == "api_key":
        scopes = context.api_key_scopes or context.permissions or []
        if not scope_allows(scopes, perm):
            raise HTTPException(status_code=403, detail=f"API key missing scope: {perm}")
        return
    if "tenant_admin" in {r.lower() for r in context.roles}:
        return
    if not has_permission(context.org_id, context.user_id, perm):
        raise HTTPException(status_code=403, detail=f"{perm} permission required")


@router.get("/sessions")
def list_sessions(context=Depends(build_request_context)) -> dict:
    _require_session_perm(context, "session.read")
    rows = session_repo.list_active_sessions(context.org_id, context.user_id)
    return {
        "request_id": context.request_id,
        "items": rows,
        "confidence": 0.99,
        "verification_status": "iam_sessions_listed",
    }


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: str,
    body: RevokeSessionRequest | None = None,
    context=Depends(build_request_context),
) -> dict:
    _require_session_perm(context, "session.revoke")
    idem_key = body.idempotency_key if body else None
    check_idempotency("iam:session_revoke", context, idem_key)
    revoked = session_repo.revoke_session(context.org_id, session_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")
    emit_session_revoked(
        org_id=context.org_id,
        user_id=context.user_id,
        session_id=session_id,
        trace_id=context.request_id,
    )
    mark_idempotency("iam:session_revoke", context, idem_key)
    return {
        "request_id": context.request_id,
        "status": "revoked",
        "session_id": session_id,
        "confidence": 0.99,
        "verification_status": "iam_session_revoked",
    }
