from datetime import datetime, timezone

from app.core.config import settings
from app.modules.core.iam.events.auth_events import emit_user_login, emit_user_logout
from app.modules.core.iam.repositories import permission_repo, user_repo
from app.modules.core.iam.services.jwt_service import issue_access_token
import hashlib

from app.modules.core.iam.services.login_rate_limiter import login_rate_limiter, refresh_rate_limiter
from app.modules.core.iam.services.password_service import verify_password
from app.modules.core.iam.services.rbac_service import list_role_names, merge_policy_context
from app.modules.core.iam.services.iam_schema_service import require_core_schema
from app.modules.core.iam.services.login_lockout_service import clear_failures, is_locked, record_failure
from app.modules.core.iam.services.mfa_service import MfaRequired, assert_mfa_gate
from app.modules.core.iam.services.token_revocation import revoke_access_token_jti
from app.services.trace import trace_span
from app.modules.core.iam.services.session_service import (
    consume_refresh_session,
    create_refresh_session,
    resolve_refresh_session,
    revoke_refresh_session,
)
from app.services.metrics import metrics_store


class AuthError(Exception):
    pass


def iam_db_enabled() -> bool:
    return bool(settings.postgres_dsn) and settings.iam_use_db_auth


def login(
    *,
    email: str,
    password: str,
    rate_limit_key: str,
    device_info: dict | None = None,
    ip_address: str | None = None,
    mfa_code: str | None = None,
) -> dict:
    with trace_span("iam.login", email=email):
        require_core_schema()
        email_part = email.split("@")[0] if "@" in email else email
        ip_part = rate_limit_key.split(":")[-1] if ":" in rate_limit_key else None
        if is_locked(email, ip_part):
            metrics_store.incr_iam_login_failure()
            raise AuthError("Account temporarily locked due to failed login attempts")

        decision = login_rate_limiter.check(rate_limit_key)
        if not decision.allowed:
            metrics_store.incr_iam_login_failure()
            raise AuthError("Too many login attempts")

        return _login_inner(email, password, device_info, ip_address, mfa_code, ip_part)


def _login_inner(
    email: str,
    password: str,
    device_info: dict | None,
    ip_address: str | None,
    mfa_code: str | None,
    ip_part: str | None,
) -> dict:
    user = user_repo.get_by_email(email)
    if user is None or user.get("status") != "active":
        record_failure(email, ip_part)
        metrics_store.incr_iam_login_failure()
        raise AuthError("Invalid credentials")
    if not verify_password(password, user.get("password_hash")):
        record_failure(email, ip_part)
        metrics_store.incr_iam_login_failure()
        raise AuthError("Invalid credentials")
    clear_failures(email, ip_part)

    org_id = user["org_id"]
    user_id = user["id"]
    roles = list_role_names(org_id, user_id)
    if not roles:
        raise AuthError("No roles assigned")

    permissions = permission_repo.list_permissions_for_user(org_id, user_id)
    attrs = merge_policy_context(org_id, user_id)
    try:
        assert_mfa_gate(org_id=org_id, user_id=user_id, attrs=attrs, mfa_code=mfa_code)
    except MfaRequired as exc:
        metrics_store.incr_iam_login_failure()
        raise AuthError(str(exc)) from exc
    raw_refresh, session_id = create_refresh_session(
        org_id=org_id,
        user_id=user_id,
        device_info=device_info,
        ip_address=ip_address,
    )
    access_token, expires_in = issue_access_token(
        user_id=user_id,
        org_id=org_id,
        roles=roles,
        permissions=permissions,
        session_id=session_id,
        attrs=attrs,
        email=user.get("email"),
    )
    user_repo.update_last_login(user_id)
    emit_user_login(org_id=org_id, user_id=user_id, session_id=session_id)
    metrics_store.incr_iam_login_success()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "expires_in": expires_in,
        "user_id": user_id,
        "org_id": org_id,
        "roles": roles,
        "permissions": permissions,
    }


def refresh(*, refresh_token: str, mfa_code: str | None = None, rate_limit_key: str | None = None) -> dict:
    with trace_span("iam.refresh"):
        require_core_schema()
        if rate_limit_key:
            decision = refresh_rate_limiter.check(rate_limit_key)
            if not decision.allowed:
                raise AuthError("Too many refresh attempts")

        session, reuse_detected = consume_refresh_session(refresh_token)
        if reuse_detected:
            from app.modules.core.iam.repositories import session_repo

            token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
            existing = session_repo.get_by_refresh_hash(token_hash)
            if existing:
                session_repo.revoke_all_for_user(existing["org_id"], existing["user_id"])
            raise AuthError("Refresh token reuse detected; all sessions revoked")
        if not session:
            raise AuthError("Invalid refresh token")

        org_id = session["org_id"]
        user_id = session["user_id"]
        session_id = session["id"]

        roles = list_role_names(org_id, user_id)
        permissions = permission_repo.list_permissions_for_user(org_id, user_id)
        attrs = merge_policy_context(org_id, user_id)
        try:
            assert_mfa_gate(org_id=org_id, user_id=user_id, attrs=attrs, mfa_code=mfa_code)
        except MfaRequired as exc:
            raise AuthError(str(exc)) from exc
        raw_refresh, new_session_id = create_refresh_session(
            org_id=org_id,
            user_id=user_id,
            rotated_from=session_id,
        )
        access_token, expires_in = issue_access_token(
            user_id=user_id,
            org_id=org_id,
            roles=roles,
            permissions=permissions,
            session_id=new_session_id,
            attrs=attrs,
        )
        metrics_store.incr_iam_token_refresh()
        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "expires_in": expires_in,
            "user_id": user_id,
            "org_id": org_id,
        }


def logout(*, org_id: str, session_id: str, user_id: str, trace_id: str = "", access_token: str | None = None) -> None:
    with trace_span("iam.logout", org_id=org_id, user_id=user_id):
        if access_token:
            revoke_access_token_jti(access_token)
        revoke_refresh_session(org_id, session_id)
        emit_user_logout(org_id=org_id, user_id=user_id, session_id=session_id)
        from app.modules.core.iam.events.role_events import emit_session_revoked

        emit_session_revoked(org_id=org_id, user_id=user_id, session_id=session_id, trace_id=trace_id or session_id)
