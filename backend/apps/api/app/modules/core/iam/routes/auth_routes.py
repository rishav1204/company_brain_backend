from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.modules.core.iam.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
)
from app.modules.core.iam.services.auth_service import AuthError, iam_db_enabled, login, logout, refresh
from app.modules.core.iam.services.iam_schema_service import IamSchemaError
from app.modules.core.iam.services.session_service import resolve_refresh_session
from app.services.jwt_auth import decode_bearer_token

router = APIRouter(tags=["iam-auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/auth/login", response_model=LoginResponse)
def auth_login(request_body: LoginRequest, request: Request) -> LoginResponse:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    rate_key = f"login:{request_body.email.lower()}:{_client_ip(request) or 'unknown'}"
    try:
        result = login(
            email=request_body.email,
            password=request_body.password,
            rate_limit_key=rate_key,
            device_info={"user_agent": request.headers.get("user-agent", "")},
            ip_address=_client_ip(request),
            mfa_code=request_body.mfa_code,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except IamSchemaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    return LoginResponse(
        request_id=f"login-{int(now.timestamp())}",
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        org_id=result["org_id"],
        roles=result["roles"],
        permissions=result["permissions"],
        confidence=0.99,
        verification_status="iam_db_login",
    )


@router.post("/auth/refresh", response_model=RefreshResponse)
def auth_refresh(request_body: RefreshRequest) -> RefreshResponse:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    try:
        result = refresh(refresh_token=request_body.refresh_token, mfa_code=request_body.mfa_code)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)
    return RefreshResponse(
        request_id=f"refresh-{int(now.timestamp())}",
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        org_id=result["org_id"],
        confidence=0.99,
        verification_status="iam_session_refreshed",
    )


@router.post("/auth/logout")
def auth_logout(
    request_body: LogoutRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    session_id = None
    org_id = None
    user_id = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            principal = decode_bearer_token(token)
            org_id = principal.org_id
            user_id = principal.user_id
            session_id = principal.session_id
        except Exception:
            pass
    if request_body.refresh_token:
        session = resolve_refresh_session(request_body.refresh_token)
        if session:
            org_id = session["org_id"]
            user_id = session["user_id"]
            session_id = session["id"]
    now = datetime.now(timezone.utc)
    access_token = None
    if authorization and authorization.lower().startswith("bearer "):
        access_token = authorization.split(" ", 1)[1].strip()
    if org_id and user_id and session_id:
        logout(
            org_id=org_id,
            session_id=session_id,
            user_id=user_id,
            trace_id=f"logout-{int(now.timestamp())}",
            access_token=access_token,
        )
    return {
        "request_id": f"logout-{int(now.timestamp())}",
        "status": "logged_out",
        "confidence": 0.99,
        "verification_status": "iam_session_revoked",
    }
