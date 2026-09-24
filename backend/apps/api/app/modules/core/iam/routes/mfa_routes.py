from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.modules.core.iam.repositories import user_repo
from app.modules.core.iam.services.device_trust_service import device_fingerprint_from_request, trust_device_for_user
from app.modules.core.iam.services.email_otp_service import send_email_otp
from app.modules.core.iam.services.mfa_service import (
    MfaInvalid,
    admin_reset_mfa,
    confirm_mfa_enrollment,
    enroll_mfa,
    user_has_mfa_enabled,
    verify_mfa_code,
)
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.modules.core.iam.services.sms_otp_service import send_sms_otp
from app.modules.core.iam.services.webauthn_service import (
    WebAuthnNotEnabled,
    begin_authentication,
    begin_registration,
    finish_authentication,
    finish_registration,
)

router = APIRouter(tags=["iam-mfa"])


class MfaConfirmBody(BaseModel):
    code: str


class TrustDeviceBody(BaseModel):
    trust_device: bool = True


class WebAuthnFinishBody(BaseModel):
    credential: dict


class RecoveryVerifyBody(BaseModel):
    code: str


@router.get("/users/me/mfa")
def mfa_status(context=Depends(build_request_context)) -> dict:
    """Return whether the current user has completed MFA enrollment."""
    enabled = user_has_mfa_enabled(context.org_id, context.user_id)
    methods = mfa_repo.list_enabled_methods(context.org_id, context.user_id)
    pending = mfa_repo.get_method(context.org_id, context.user_id, "totp")
    enrollment_pending = bool(
        pending
        and not pending.get("enabled")
        and (pending.get("metadata") or {}).get("secret")
    )
    return {
        "request_id": context.request_id,
        "mfa_enabled": enabled,
        "methods": [str(m.get("method")) for m in methods],
        "enrollment_pending": enrollment_pending and not enabled,
        "confidence": 0.99,
        "verification_status": "mfa_status",
    }


@router.post("/users/me/mfa/enroll")
def mfa_enroll(context=Depends(build_request_context)) -> dict:
    if user_has_mfa_enabled(context.org_id, context.user_id):
        raise HTTPException(
            status_code=409,
            detail="MFA is already enabled for this account",
        )
    try:
        result = enroll_mfa(context.org_id, context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "secret": result["secret"],
        "provisioning_uri": result["provisioning_uri"],
        "qr_code_data_url": result.get("qr_code_data_url"),
        "issuer": result.get("issuer"),
        "account_name": result.get("account_name"),
        "confidence": 0.99,
        "verification_status": "mfa_enrollment_started",
    }


@router.post("/users/me/mfa/confirm")
def mfa_confirm(body: MfaConfirmBody, context=Depends(build_request_context)) -> dict:
    try:
        recovery_codes = confirm_mfa_enrollment(context.org_id, context.user_id, body.code)
    except MfaInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "status": "mfa_enabled",
        "recovery_codes": recovery_codes,
        "confidence": 0.99,
        "verification_status": "mfa_enrollment_confirmed",
    }


@router.post("/users/me/mfa/email/send")
def mfa_email_send(context=Depends(build_request_context)) -> dict:
    user = user_repo.get_by_id(context.org_id, context.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    send_email_otp(context.org_id, context.user_id, user["email"])
    return {"request_id": context.request_id, "status": "email_otp_sent"}


@router.post("/users/me/mfa/sms/send")
def mfa_sms_send(context=Depends(build_request_context)) -> dict:
    user = user_repo.get_by_id(context.org_id, context.user_id)
    phone = (user or {}).get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number not configured")
    try:
        send_sms_otp(context.org_id, context.user_id, phone)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"request_id": context.request_id, "status": "sms_otp_sent"}


@router.post("/users/me/mfa/webauthn/register/begin")
def webauthn_register_begin(context=Depends(build_request_context)) -> dict:
    user = user_repo.get_by_id(context.org_id, context.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        return begin_registration(context.org_id, context.user_id, user["email"])
    except WebAuthnNotEnabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/users/me/mfa/webauthn/register/finish")
def webauthn_register_finish(body: WebAuthnFinishBody, context=Depends(build_request_context)) -> dict:
    try:
        finish_registration(context.org_id, context.user_id, body.credential)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "status": "webauthn_registered"}


@router.post("/users/me/mfa/webauthn/authenticate/begin")
def webauthn_auth_begin(context=Depends(build_request_context)) -> dict:
    try:
        return begin_authentication(context.org_id, context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/users/me/mfa/webauthn/authenticate/finish")
def webauthn_auth_finish(body: WebAuthnFinishBody, context=Depends(build_request_context)) -> dict:
    ok = finish_authentication(context.org_id, context.user_id, body.credential)
    if not ok:
        raise HTTPException(status_code=401, detail="WebAuthn verification failed")
    return {"request_id": context.request_id, "status": "webauthn_verified"}


@router.post("/users/me/mfa/recovery/verify")
def recovery_verify(body: RecoveryVerifyBody, context=Depends(build_request_context)) -> dict:
    if not verify_mfa_code(context.org_id, context.user_id, body.code):
        raise HTTPException(status_code=401, detail="Invalid recovery code")
    return {"request_id": context.request_id, "status": "recovery_verified"}


@router.post("/users/me/mfa/trust-device")
def trust_device(body: TrustDeviceBody, context=Depends(build_request_context)) -> dict:
    if not body.trust_device:
        return {"request_id": context.request_id, "status": "skipped"}
    ua = context.user_agent or ""
    fingerprint = device_fingerprint_from_request(user_agent=ua, ip_address=context.ip_address)
    trust_device_for_user(context.org_id, context.user_id, fingerprint, {"user_agent": ua})
    return {"request_id": context.request_id, "status": "device_trusted"}


@router.post("/admin/users/{user_id}/mfa/reset")
def admin_mfa_reset(user_id: str, context=Depends(build_request_context)) -> dict:
    from app.modules.core.iam.routes.admin_routes import _require_admin

    _require_admin(context)
    admin_reset_mfa(context.org_id, user_id)
    return {"request_id": context.request_id, "status": "mfa_reset", "user_id": user_id}
