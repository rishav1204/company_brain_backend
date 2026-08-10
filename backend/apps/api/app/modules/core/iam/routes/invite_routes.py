from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.routes.idempotency_helper import check_idempotency, mark_idempotency
from app.modules.core.iam.middleware.mutation_guard import require_db_mutation
from app.modules.core.iam.services.api_key_auth_service import scope_allows
from app.modules.core.iam.services.invite_service import accept_invite, create_invite
from pydantic import BaseModel, Field


class InviteRequest(BaseModel):
    email: str
    role_name: str
    company_id: str | None = None
    branch_id: str | None = None
    idempotency_key: str | None = None


class AcceptInviteRequest(BaseModel):
    invite_token: str
    password: str
    display_name: str


router = APIRouter(tags=["iam-invites"])


def _require_user_manage(context) -> None:
    if context.auth_method == "api_key":
        scopes = context.api_key_scopes or context.permissions or []
        if not scope_allows(scopes, "user.manage"):
            raise HTTPException(status_code=403, detail="API key missing scope: user.manage")
        return
    require_db_mutation(
        context,
        ["user.manage"],
        detail="user.manage permission required",
        allow_tenant_admin=True,
    )


@router.post("/users/invites")
def invite_user(body: InviteRequest, context=Depends(build_request_context)) -> dict:
    _require_user_manage(context)
    check_idempotency("iam:invite", context, body.idempotency_key)
    try:
        result = create_invite(
            org_id=context.org_id,
            email=body.email,
            role_name=body.role_name,
            invited_by=context.user_id,
            trace_id=context.request_id,
            company_id=body.company_id,
            branch_id=body.branch_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mark_idempotency("iam:invite", context, body.idempotency_key)
    return {
        "request_id": context.request_id,
        **result,
        "confidence": 0.99,
        "verification_status": "user_invited",
    }


@router.post("/auth/invite/accept")
def accept_user_invite(body: AcceptInviteRequest) -> dict:
    try:
        user = accept_invite(
            invite_token=body.invite_token,
            password=body.password,
            display_name=body.display_name,
            trace_id="invite-accept",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "request_id": "invite-accept",
        "user_id": user["id"],
        "email": user["email"],
        "org_id": user["org_id"],
        "confidence": 0.99,
        "verification_status": "invite_accepted",
    }
