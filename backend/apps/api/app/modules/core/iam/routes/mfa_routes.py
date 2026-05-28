from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.mfa_service import MfaInvalid, confirm_mfa_enrollment, enroll_mfa

router = APIRouter(tags=["iam-mfa"])


@router.post("/users/me/mfa/enroll")
def mfa_enroll(context=Depends(build_request_context)) -> dict:
    try:
        result = enroll_mfa(context.org_id, context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "provisioning_uri": result["provisioning_uri"],
        "confidence": 0.99,
        "verification_status": "mfa_enrollment_started",
    }


@router.post("/users/me/mfa/confirm")
def mfa_confirm(code: str, context=Depends(build_request_context)) -> dict:
    try:
        confirm_mfa_enrollment(context.org_id, context.user_id, code)
    except MfaInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "status": "mfa_enabled",
        "confidence": 0.99,
        "verification_status": "mfa_enrollment_confirmed",
    }
