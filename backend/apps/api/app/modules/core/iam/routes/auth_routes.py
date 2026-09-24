from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from app.api.deps import build_request_context
from app.core.sse_token_service import issue_sse_token

from app.core.config import settings
from app.modules.core.iam.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MfaVerifyRequest,
    RefreshRequest,
    RefreshResponse,
)
from app.modules.core.iam.services.auth_cookies import clear_access_token_cookie, set_access_token_cookie
from app.modules.core.iam.services.auth_service import (
    AuthError,
    complete_mfa_login,
    iam_db_enabled,
    login,
    logout,
    refresh,
)
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


def _login_response(result: dict, *, status: str) -> LoginResponse:
    now = datetime.now(timezone.utc)
    if result.get("mfa_required"):
        return LoginResponse(
            request_id=f"login-{int(now.timestamp())}",
            mfa_required=True,
            mfa_challenge_token=result.get("mfa_challenge_token"),
            user_id=result.get("user_id"),
            org_id=result.get("org_id"),
            confidence=0.99,
            verification_status="mfa_challenge",
        )
    return LoginResponse(
        request_id=f"login-{int(now.timestamp())}",
        mfa_required=False,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user_id=result["user_id"],
        org_id=result["org_id"],
        roles=result.get("roles") or [],
        permissions=result.get("permissions") or [],
        confidence=0.99,
        verification_status=status,
    )


@router.post("/auth/login", response_model=LoginResponse)
def auth_login(request_body: LoginRequest, request: Request, response: Response) -> LoginResponse:
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
            org_id=request_body.org_id,
            org_slug=request_body.org_slug,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except IamSchemaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if result.get("mfa_required"):
        return _login_response(result, status="mfa_challenge")

    set_access_token_cookie(response, result["access_token"], max_age=result["expires_in"])
    return _login_response(result, status="iam_db_login")


@router.post("/auth/mfa/verify", response_model=LoginResponse)
def auth_mfa_verify(request_body: MfaVerifyRequest, request: Request, response: Response) -> LoginResponse:
    """Complete login after password step using TOTP / recovery code."""
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    try:
        result = complete_mfa_login(
            mfa_challenge_token=request_body.mfa_challenge_token,
            code=request_body.code,
            device_info={"user_agent": request.headers.get("user-agent", "")},
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except IamSchemaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    set_access_token_cookie(response, result["access_token"], max_age=result["expires_in"])
    return _login_response(result, status="iam_db_login_mfa")


@router.post("/auth/sse-token")
def auth_sse_token(context=Depends(build_request_context)) -> dict:
    """Issue short-lived token for EventSource streams (SEC-03).

    Prefer ``?sse_token=`` on the stream URL (EventSource cannot set headers).
    ``X-SSE-Token`` header is also accepted for fetch-based clients.
    """
    raw, ttl = issue_sse_token(
        org_id=context.org_id,
        user_id=context.user_id,
        session_id=context.session_id,
    )
    return {"sse_token": raw, "expires_in": ttl}


@router.post("/auth/refresh", response_model=RefreshResponse)
def auth_refresh(request_body: RefreshRequest, request: Request, response: Response) -> RefreshResponse:
    if not iam_db_enabled():
        raise HTTPException(status_code=503, detail="IAM database authentication is not enabled")
    rate_key = f"refresh:{_client_ip(request) or 'unknown'}"
    try:
        result = refresh(
            refresh_token=request_body.refresh_token,
            mfa_code=request_body.mfa_code,
            rate_limit_key=rate_key,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except IamSchemaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    set_access_token_cookie(response, result["access_token"], max_age=result["expires_in"])
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
    response: Response,
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
    clear_access_token_cookie(response)
    return {
        "request_id": f"logout-{int(now.timestamp())}",
        "status": "logged_out",
        "confidence": 0.99,
        "verification_status": "iam_session_revoked",
    }
