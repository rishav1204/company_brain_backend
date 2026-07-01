from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.services.auth_service import iam_db_enabled
from app.modules.core.iam.services.password_lifecycle_service import (
    PasswordLifecycleError,
    change_password,
    confirm_password_reset,
    request_password_reset,
)

router = APIRouter(tags=["iam-password"])


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12)


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12)


@router.post("/auth/password/change")
def password_change(body: PasswordChangeRequest, context=Depends(build_request_context)) -> dict:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    try:
        change_password(
            org_id=context.org_id,
            user_id=context.user_id,
            current_password=body.current_password,
            new_password=body.new_password,
            current_session_id=context.session_id,
        )
    except PasswordLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "status": "password_changed",
        "verification_status": "iam_password_changed",
    }


@router.post("/auth/password/reset/request")
def password_reset_request(body: PasswordResetRequest) -> dict:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    request_password_reset(body.email.strip())
    return {
        "request_id": "password-reset-request",
        "status": "reset_email_sent_if_account_exists",
        "verification_status": "iam_password_reset_requested",
    }


@router.post("/auth/password/reset/confirm")
def password_reset_confirm(body: PasswordResetConfirmRequest) -> dict:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    try:
        confirm_password_reset(body.token, body.new_password)
    except PasswordLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "request_id": "password-reset-confirm",
        "status": "password_reset",
        "verification_status": "iam_password_reset_confirmed",
    }
