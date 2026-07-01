from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.modules.core.iam.services.auth_service import AuthError, iam_db_enabled
from app.modules.core.iam.services.device_trust_service import device_fingerprint_from_request
from app.modules.core.iam.services.oidc_service import iam_oidc_service

router = APIRouter(tags=["iam-oidc"])


class OidcCallbackBody(BaseModel):
    code: str
    state: str
    mfa_code: str | None = None
    trust_device: bool = False


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/auth/oidc/start")
def oidc_start(redirect_uri: str | None = None) -> dict:
    if not iam_oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        start = iam_oidc_service.start_authorize(redirect_uri=redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)
    return {
        "request_id": f"oidc-start-{int(now.timestamp())}",
        "authorize_url": start["authorize_url"],
        "state": start["state"],
        "confidence": 0.98,
        "verification_status": "oidc_authorize_ready",
    }


@router.post("/auth/oidc/callback")
def oidc_callback(body: OidcCallbackBody, request: Request) -> dict:
    if not iam_oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is required for OIDC")
    ua = request.headers.get("user-agent", "")
    fingerprint = device_fingerprint_from_request(user_agent=ua)
    try:
        exchange = iam_oidc_service.callback_exchange(code=body.code, state=body.state)
        session = iam_oidc_service.complete_login(
            exchange["claims"],
            device_info={"user_agent": ua},
            ip_address=_client_ip(request),
            mfa_code=body.mfa_code,
            device_fingerprint=fingerprint,
            trust_device=body.trust_device,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"OIDC callback failed: {exc}") from exc
    now = datetime.now(timezone.utc)
    return {
        "request_id": f"oidc-callback-{int(now.timestamp())}",
        "access_token": session["access_token"],
        "refresh_token": session.get("refresh_token"),
        "expires_in": session["expires_in"],
        "user_id": session["user_id"],
        "org_id": session["org_id"],
        "confidence": 0.98,
        "verification_status": "iam_oidc_session_issued",
    }
