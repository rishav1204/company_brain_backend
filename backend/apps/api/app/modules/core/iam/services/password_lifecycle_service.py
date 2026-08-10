import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.modules.core.iam.repositories import session_repo, user_repo
from app.modules.core.iam.services.auth_audit_service import record_auth_event
from app.modules.core.iam.services.password_service import hash_password, verify_password
from app.modules.core.iam.validators.password_validator import validate_password_strength


class PasswordLifecycleError(Exception):
    pass


def change_password(
    *,
    org_id: str,
    user_id: str,
    current_password: str,
    new_password: str,
    current_session_id: str | None = None,
) -> None:
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        raise PasswordLifecycleError("User not found")
    full = user_repo.get_by_email(user["email"])
    if not full or not verify_password(current_password, full.get("password_hash")):
        record_auth_event(event="password_change", success=False, org_id=org_id, user_id=user_id, reason="invalid_current")
        raise PasswordLifecycleError("Current password is incorrect")
    validate_password_strength(new_password)
    new_hash = hash_password(new_password)
    if user_repo.password_in_history(user_id, new_hash):
        raise PasswordLifecycleError("Password was used recently")
    user_repo.update_password(org_id, user_id, new_hash)
    session_repo.revoke_all_for_user(org_id, user_id)
    if current_session_id:
        session_repo.revoke_session(org_id, current_session_id)
    record_auth_event(event="password_change", success=True, org_id=org_id, user_id=user_id)


def request_password_reset(email: str) -> str | None:
    user = user_repo.get_by_email(email)
    if not user or user.get("status") != "active":
        return None
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    user_repo.create_reset_token(user["id"], token_hash, expires)
    record_auth_event(
        event="password_reset_request",
        success=True,
        org_id=user["org_id"],
        user_id=user["id"],
        metadata={"email": email},
    )
    _send_reset_email(user["email"], raw_token)
    return raw_token


def confirm_password_reset(token: str, new_password: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = user_repo.consume_reset_token(token_hash)
    if not row:
        record_auth_event(event="password_reset_confirm", success=False, reason="invalid_token")
        raise PasswordLifecycleError("Invalid or expired reset token")
    user_id = row["user_id"]
    from app.services.db import get_db_conn

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT org_id::text AS org_id FROM core.users WHERE id = %s::uuid", (user_id,))
            user_row = cur.fetchone()
    if not user_row:
        raise PasswordLifecycleError("User not found")
    org_id = user_row["org_id"]
    validate_password_strength(new_password)
    new_hash = hash_password(new_password)
    user_repo.update_password(org_id, user_id, new_hash)
    session_repo.revoke_all_for_user(org_id, user_id)
    record_auth_event(event="password_reset_confirm", success=True, org_id=org_id, user_id=user_id)


def _send_reset_email(email: str, token: str) -> None:
    if not settings.password_reset_email_enabled:
        return
    try:
        from app.modules.platform.notifications.services.email_service import EmailDeliveryError, email_service

        reset_url = f"{settings.app_public_base_url.rstrip('/')}/reset-password?token={token}"
        email_service.send_email(
            to=email,
            subject="Password reset request",
            body=f"Use this link to reset your password (valid 1 hour): {reset_url}",
        )
    except EmailDeliveryError:
        raise
    except Exception:
        pass
