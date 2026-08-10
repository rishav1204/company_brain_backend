from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings, DEV_ORG_ID
from app.api.deps import build_request_context
from app.schemas.auth import (
    DevCreateUserRequest,
    DevCreateUserResponse,
    MeResponse,
    OidcCallbackRequest,
    OidcCallbackResponse,
    OidcLogoutRequest,
    OidcRefreshRequest,
    OidcRefreshResponse,
    OidcRevokeRequest,
    OidcStartResponse,
    PasswordLoginRequest,
    PasswordLoginResponse,
    PermissionEvaluateRequest,
    PermissionEvaluateResponse,
)
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.core.iam.services.auth_service import AuthError, iam_db_enabled, login as iam_login
from app.services.dev_auth_store import dev_auth_store
from app.services.object_context import resolve_object_context
from app.services.oidc_service import oidc_service

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=MeResponse)
def me(context=Depends(build_request_context)) -> MeResponse:
    return MeResponse(
        request_id=context.request_id,
        user_id=context.user_id,
        org_id=context.org_id,
        roles=context.roles,
        permissions=context.permissions or [],
        session_id=context.session_id,
        confidence=1.0,
        verification_status="verified",
    )


@router.get("/permissions/evaluate", response_model=PermissionEvaluateResponse)
def permissions_evaluate(
    object_type: str,
    object_id: str,
    action: str,
    context=Depends(build_request_context),
) -> PermissionEvaluateResponse:
    _ = PermissionEvaluateRequest(object_type=object_type, object_id=object_id, action=action)
    object_context = resolve_object_context(
        org_id=context.org_id,
        object_type=object_type,
        object_id=object_id,
    )
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles,
        action=action,
        object_context=object_context,
        attrs=context.attrs,
        created_by=object_context.owner_user_id,
        emit_denial_event=iam_db_enabled(),
    )
    return PermissionEvaluateResponse(
        request_id=context.request_id,
        allowed=decision.allowed,
        reason=decision.reason,
        checks=decision.checks or [],
        object_context=object_context.as_summary(),
        confidence=0.99,
        verification_status="object_context_policy_checked",
    )


@router.post("/auth/password/login", response_model=PasswordLoginResponse)
def password_login(request: PasswordLoginRequest) -> PasswordLoginResponse:
    if settings.auth_mode != "bearer_only":
        raise HTTPException(status_code=403, detail="Password login route is only available in bearer-only auth mode")
    if not settings.dev_auth_routes_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    if not request.email.strip() or not request.password.strip():
        raise HTTPException(status_code=400, detail="Email and password are required")

    # Legacy route remains a local/dev JWT mint when dev auth routes are on.
    # Production IAM password login is POST /auth/login (modular IAM schema).
    # Optional org-scoped IAM path only when org is explicitly non-default.
    if (
        iam_db_enabled()
        and request.org_id
        and str(request.org_id) != str(DEV_ORG_ID)
        and request.password != "dev-password"
    ):
        try:
            result = iam_login(
                email=request.email,
                password=request.password,
                rate_limit_key=f"login:{request.email.lower()}",
                org_id=request.org_id,
            )
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        now = datetime.now(timezone.utc)
        return PasswordLoginResponse(
            request_id=f"login-{int(now.timestamp())}",
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            expires_in=result["expires_in"],
            user_id=result.get("user_id"),
            org_id=result.get("org_id"),
            confidence=0.99,
            verification_status="iam_db_password_login",
        )

    # Dev compatibility route: replace this with IdP exchange API in production.
    dev_user = dev_auth_store.get_user(request.email)
    if dev_user is None:
        if request.password != "dev-password":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        resolved_org_id = DEV_ORG_ID
        resolved_roles = ["viewer"]
    else:
        if request.password != dev_user["password"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        resolved_org_id = dev_user["org_id"]
        resolved_roles = dev_user["roles"]

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    token_payload = {
        settings.jwt_tenant_claim: resolved_org_id,
        settings.jwt_user_claim: request.email,
        settings.jwt_roles_claim: resolved_roles if not request.roles else list(request.roles),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "session_id": "00000000-0000-4000-8000-0000000000de",
    }
    if request.org_id and str(request.org_id).strip() and str(request.org_id) != "org-demo":
        token_payload[settings.jwt_tenant_claim] = str(request.org_id)
        resolved_org_id = str(request.org_id)
    token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return PasswordLoginResponse(
        request_id=f"login-{int(now.timestamp())}",
        access_token=token,
        expires_in=3600,
        user_id=request.email,
        org_id=resolved_org_id,
        confidence=0.9,
        verification_status="dev_password_exchange",
    )


@router.post("/auth/dev/create-user", response_model=DevCreateUserResponse)
def dev_create_user(request: DevCreateUserRequest) -> DevCreateUserResponse:
    if settings.auth_mode != "bearer_only":
        raise HTTPException(status_code=403, detail="Dev create-user route is only available in bearer-only auth mode")
    if not settings.dev_auth_routes_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    if not request.email.strip() or not request.password.strip():
        raise HTTPException(status_code=400, detail="Email and password are required")
    allowed_dev_roles = {"viewer", "preparer", "ap_executive"}
    requested_roles = [r for r in request.roles if r in allowed_dev_roles] or ["viewer"]
    target_org_id = DEV_ORG_ID
    if iam_db_enabled():
        from app.modules.core.iam.repositories import role_repo, user_repo
        from app.modules.core.iam.services.password_service import hash_password
        from app.modules.core.iam.validators.password_validator import validate_password_strength
        from app.modules.core.iam.events.user_events import emit_user_created
        from app.modules.core.iam.events.role_events import emit_role_assigned

        try:
            validate_password_strength(request.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        display = request.display_name or request.email.split("@")[0]
        created = user_repo.create_user(
            org_id=target_org_id,
            email=request.email,
            display_name=display,
            password_hash=hash_password(request.password),
        )
        for role_name in requested_roles:
            role = role_repo.get_role_by_name(request.org_id, role_name)
            if role:
                user_repo.assign_role(request.org_id, created["id"], role["id"])
        trace = f"dev-create-{int(datetime.now(timezone.utc).timestamp())}"
        emit_user_created(org_id=target_org_id, user_id=created["id"], email=created["email"], trace_id=trace)
        for role_name in requested_roles:
            emit_role_assigned(org_id=target_org_id, user_id=created["id"], role_name=role_name, trace_id=trace)
        return DevCreateUserResponse(
            request_id=trace,
            user_id=created["id"],
            email=created["email"],
            org_id=created["org_id"],
            roles=requested_roles,
            confidence=0.99,
            verification_status="iam_dev_user_created",
        )

    user = dev_auth_store.create_user(
        email=request.email,
        password=request.password,
        org_id=target_org_id,
        roles=requested_roles,
        display_name=request.display_name,
    )
    return DevCreateUserResponse(
        request_id=f"dev-create-{int(datetime.now(timezone.utc).timestamp())}",
        user_id=user["user_id"],
        email=user["email"],
        org_id=user["org_id"],
        roles=requested_roles,
        confidence=0.88,
        verification_status="dev_user_created",
    )


@router.get("/auth/oidc/start", response_model=OidcStartResponse)
def oidc_start(redirect_uri: str | None = None) -> OidcStartResponse:
    if not oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        start = oidc_service.start_authorize(redirect_uri=redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    request_id = f"oidc-start-{int(datetime.now(timezone.utc).timestamp())}"
    return OidcStartResponse(
        request_id=request_id,
        authorize_url=start["authorize_url"],
        state=start["state"],
        confidence=0.98,
        verification_status="oidc_authorize_ready",
    )


@router.post("/auth/oidc/callback", response_model=OidcCallbackResponse)
def oidc_callback(request: OidcCallbackRequest) -> OidcCallbackResponse:
    if not oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        exchange = oidc_service.callback_exchange(code=request.code, state=request.state)
        claims = exchange["claims"]
        if iam_db_enabled():
            from app.modules.core.iam.repositories import user_repo
            from app.modules.core.iam.services.mfa_service import MfaRequired, assert_mfa_gate
            from app.modules.core.iam.services.rbac_service import merge_policy_context

            org_id = str(claims.get(settings.jwt_tenant_claim) or claims.get(settings.oidc_org_claim) or "")
            user_id = str(claims.get(settings.jwt_user_claim) or claims.get(settings.oidc_user_claim) or claims.get("sub") or "")
            if org_id and user_id:
                attrs = merge_policy_context(org_id, user_id)
                try:
                    assert_mfa_gate(org_id=org_id, user_id=user_id, attrs=attrs, mfa_code=request.mfa_code)
                except MfaRequired as exc:
                    raise HTTPException(status_code=401, detail=str(exc)) from exc
        session = oidc_service.issue_api_session(
            exchange["claims"],
            upstream_access_token=exchange.get("access_token"),
            upstream_id_token=exchange.get("id_token"),
            provider_refresh_token=exchange.get("refresh_token"),
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"OIDC callback failed: {exc}") from exc
    request_id = f"oidc-callback-{int(datetime.now(timezone.utc).timestamp())}"
    return OidcCallbackResponse(
        request_id=request_id,
        access_token=session["access_token"],
        expires_in=session["expires_in"],
        user_id=session["user_id"],
        org_id=session["org_id"],
        refresh_token=session.get("refresh_token"),
        confidence=0.98,
        verification_status="oidc_session_issued",
    )


@router.post("/auth/oidc/refresh", response_model=OidcRefreshResponse)
def oidc_refresh(request: OidcRefreshRequest) -> OidcRefreshResponse:
    if not oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        refreshed = oidc_service.refresh_api_session(refresh_token=request.refresh_token)
        if iam_db_enabled():
            from app.modules.core.iam.services.mfa_service import MfaRequired, assert_mfa_gate
            from app.services.jwt_auth import decode_bearer_token

            principal = decode_bearer_token(refreshed["access_token"])
            try:
                assert_mfa_gate(
                    org_id=principal.org_id,
                    user_id=principal.user_id,
                    attrs=principal.attrs,
                    mfa_code=request.mfa_code,
                )
            except MfaRequired as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"OIDC refresh failed: {exc}") from exc
    request_id = f"oidc-refresh-{int(datetime.now(timezone.utc).timestamp())}"
    return OidcRefreshResponse(
        request_id=request_id,
        access_token=refreshed["access_token"],
        expires_in=refreshed["expires_in"],
        user_id=refreshed["user_id"],
        org_id=refreshed["org_id"],
        confidence=0.98,
        verification_status="oidc_session_refreshed",
    )


@router.post("/auth/oidc/revoke")
def oidc_revoke(request: OidcRevokeRequest) -> dict:
    if not oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        oidc_service.revoke_access_token(access_token=request.access_token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OIDC revoke failed: {exc}") from exc
    return {
        "request_id": f"oidc-revoke-{int(datetime.now(timezone.utc).timestamp())}",
        "status": "revoked",
        "confidence": 0.98,
        "verification_status": "oidc_access_token_revoked",
    }


@router.post("/auth/oidc/logout")
def oidc_logout(request: OidcLogoutRequest) -> dict:
    if not oidc_service.is_enabled():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    oidc_service.logout(refresh_token=request.refresh_token, access_token=request.access_token)
    return {
        "request_id": f"oidc-logout-{int(datetime.now(timezone.utc).timestamp())}",
        "status": "logged_out",
        "confidence": 0.98,
        "verification_status": "oidc_session_terminated",
    }
