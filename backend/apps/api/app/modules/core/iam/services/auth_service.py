from datetime import datetime, timezone
import threading

from app.core.config import settings
from app.modules.core.iam.events.auth_events import emit_user_login, emit_user_logout
from app.modules.core.iam.repositories import permission_repo, user_repo
from app.modules.core.iam.services.jwt_service import issue_access_token
import hashlib

from app.modules.core.iam.services.login_rate_limiter import login_rate_limiter, refresh_rate_limiter
from app.modules.core.iam.services.password_service import verify_password
from app.modules.core.iam.services.rbac_service import list_role_names, merge_policy_context, merge_policy_context_from_rows
from app.modules.core.iam.services.iam_schema_service import require_core_schema
from app.modules.core.iam.services.login_lockout_service import clear_failures, is_locked, record_failure
from app.modules.core.iam.services.mfa_service import MfaRequired, assert_mfa_gate
from app.modules.core.iam.services.auth_audit_service import record_auth_event
from app.modules.core.iam.services.session_policy_service import enforce_concurrent_session_limit
from app.modules.core.iam.services.token_revocation import revoke_access_token_jti
from app.services.trace import trace_span
from app.modules.core.iam.services.refresh_grace import get_grace_result, store_grace_result
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
    org_id: str | None = None,
    org_slug: str | None = None,
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

        return _login_inner(email, password, device_info, ip_address, mfa_code, ip_part, org_id, org_slug)


def _defer_login_side_effects(
    *,
    user_id: str,
    org_id: str,
    session_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    def _run() -> None:
        try:
            user_repo.update_last_login(user_id)
            emit_user_login(org_id=org_id, user_id=user_id, session_id=session_id)
            record_auth_event(
                event="login",
                success=True,
                org_id=org_id,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def _login_inner(
    email: str,
    password: str,
    device_info: dict | None,
    ip_address: str | None,
    mfa_code: str | None,
    ip_part: str | None,
    org_id_hint: str | None = None,
    org_slug_hint: str | None = None,
) -> dict:
    bundle = user_repo.get_login_bundle(email, org_id=org_id_hint, org_slug=org_slug_hint)
    if bundle and bundle.get("ambiguous"):
        # Same email in 2+ orgs — the UI must re-submit with org_id or org_slug.
        raise AuthError("org_id or org_slug is required for login")
    user = bundle["user"] if bundle else None
    if user is None or user.get("status") != "active":
        record_failure(email, ip_part)
        metrics_store.incr_iam_login_failure()
        record_auth_event(event="login", success=False, reason="invalid_credentials", ip_address=ip_address, user_agent=(device_info or {}).get("user_agent"))
        raise AuthError("Invalid credentials")
    if not verify_password(password, user.get("password_hash")):
        record_failure(email, ip_part)
        metrics_store.incr_iam_login_failure()
        record_auth_event(event="login", success=False, org_id=user.get("org_id"), user_id=user.get("id"), reason="invalid_credentials", ip_address=ip_address, user_agent=(device_info or {}).get("user_agent"))
        raise AuthError("Invalid credentials")
    clear_failures(email, ip_part)

    org_id = user["org_id"]
    user_id = user["id"]
    try:
        from app.modules.platform.control_plane.services.access_config_service import (
            access_config_service,
        )

        controls = access_config_service.get_org_controls(str(org_id))
        if not controls.get("login_allowed", True) or str(
            controls.get("lifecycle_status") or "active"
        ) in {"frozen", "suspended", "offboarding"}:
            metrics_store.incr_iam_login_failure()
            record_auth_event(
                event="login",
                success=False,
                org_id=org_id,
                user_id=user_id,
                reason="org_login_disabled",
                ip_address=ip_address,
            )
            raise AuthError("Organization access is currently disabled")
    except AuthError:
        raise
    except Exception:
        pass
    roles = bundle.get("roles") or []
    if not roles:
        raise AuthError("No roles assigned")

    permissions = bundle.get("permissions") or []
    attrs = merge_policy_context_from_rows(bundle.get("role_rows") or [])
    try:
        assert_mfa_gate(org_id=org_id, user_id=user_id, attrs=attrs, mfa_code=mfa_code)
    except MfaRequired as exc:
        metrics_store.incr_iam_login_failure()
        record_auth_event(event="login", success=False, org_id=org_id, user_id=user_id, reason="mfa_required", ip_address=ip_address)
        raise AuthError(str(exc)) from exc
    enforce_concurrent_session_limit(org_id, user_id)
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
    _defer_login_side_effects(
        user_id=user_id,
        org_id=org_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=(device_info or {}).get("user_agent"),
    )
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

        grace = get_grace_result(refresh_token)
        if grace:
            metrics_store.incr_iam_token_refresh()
            return grace

        session, reuse_detected = consume_refresh_session(refresh_token)
        if reuse_detected:
            grace = get_grace_result(refresh_token)
            if grace:
                metrics_store.incr_iam_token_refresh()
                return grace
            from app.modules.core.iam.repositories import session_repo

            token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
            existing = session_repo.get_by_refresh_hash(token_hash)
            if existing:
                session_repo.revoke_all_for_user(existing["org_id"], existing["user_id"])
                record_auth_event(
                    event="refresh_reuse",
                    success=False,
                    org_id=existing["org_id"],
                    user_id=existing["user_id"],
                    reason="reuse_detected",
                )
            raise AuthError("Refresh token reuse detected; all sessions revoked")
        if not session:
            grace = get_grace_result(refresh_token)
            if grace:
                metrics_store.incr_iam_token_refresh()
                return grace
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
        result = {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "expires_in": expires_in,
            "user_id": user_id,
            "org_id": org_id,
        }
        store_grace_result(refresh_token, result)
        from app.modules.core.iam.repositories import session_repo as _session_repo

        _session_repo.touch_last_active(org_id, new_session_id)
        record_auth_event(event="refresh", success=True, org_id=org_id, user_id=user_id, session_id=new_session_id)
        return result


def logout(*, org_id: str, session_id: str, user_id: str, trace_id: str = "", access_token: str | None = None) -> None:
    with trace_span("iam.logout", org_id=org_id, user_id=user_id):
        if access_token:
            revoke_access_token_jti(access_token)
        revoke_refresh_session(org_id, session_id)
        emit_user_logout(org_id=org_id, user_id=user_id, session_id=session_id)
        from app.modules.core.iam.events.role_events import emit_session_revoked

        emit_session_revoked(org_id=org_id, user_id=user_id, session_id=session_id, trace_id=trace_id or session_id)
        record_auth_event(event="logout", success=True, org_id=org_id, user_id=user_id, session_id=session_id)
