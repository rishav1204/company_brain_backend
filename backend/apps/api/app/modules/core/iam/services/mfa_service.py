import base64
import secrets
import uuid

import pyotp

from app.modules.core.iam.repositories import user_repo
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.modules.core.iam.services.email_otp_service import verify_email_otp
from app.modules.core.iam.services.sms_otp_service import verify_sms_otp
from app.modules.core.iam.services.webauthn_service import finish_authentication


class MfaRequired(Exception):
    pass


class MfaInvalid(Exception):
    pass


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, email: str, secret: str, issuer: str = "FinanceOS") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(str(code).strip(), valid_window=1)


def _totp_secret(org_id: str, user_id: str) -> str | None:
    row = mfa_repo.get_method(org_id, user_id, "totp")
    if row:
        meta = row.get("metadata") or {}
        secret = meta.get("secret")
        if secret:
            return str(secret)
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        return None
    with __import__("app.services.db", fromlist=["get_db_conn"]).get_db_conn() as conn:
        from app.services.db import set_rls_org

        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute("SELECT mfa_secret FROM core.users WHERE id = %s::uuid", (user_id,))
            legacy = cur.fetchone()
    return (legacy or {}).get("mfa_secret")


def enroll_mfa(org_id: str, user_id: str) -> dict:
    secret = generate_totp_secret()
    mfa_repo.upsert_method(org_id, user_id, "totp", enabled=False, metadata={"secret": secret})
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        raise ValueError("User not found")
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri(email=user["email"], secret=secret),
    }


def confirm_mfa_enrollment(org_id: str, user_id: str, code: str) -> list[str]:
    secret = _totp_secret(org_id, user_id)
    if not secret or not verify_totp(secret, code):
        raise MfaInvalid("Invalid MFA code")
    mfa_repo.upsert_method(org_id, user_id, "totp", enabled=True, metadata={"secret": secret})
    with __import__("app.services.db", fromlist=["get_db_conn"]).get_db_conn() as conn:
        from app.services.db import set_rls_org

        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE core.users SET mfa_enabled = TRUE, mfa_secret = %s, updated_at = NOW() WHERE id = %s::uuid",
                (secret, user_id),
            )
    batch_id = str(uuid.uuid4())
    plain_codes = mfa_repo.generate_recovery_codes()
    hashes = [mfa_repo.hash_recovery_code(c) for c in plain_codes]
    mfa_repo.store_recovery_codes(org_id, user_id, hashes, batch_id)
    from app.modules.core.iam.services.auth_audit_service import record_auth_event

    record_auth_event(event="mfa_enroll", success=True, org_id=org_id, user_id=user_id)
    return plain_codes


def verify_mfa_code(
    org_id: str,
    user_id: str,
    code: str,
    *,
    webauthn_assertion: dict | None = None,
) -> bool:
    code = str(code or "").strip()
    if webauthn_assertion and finish_authentication(org_id, user_id, webauthn_assertion):
        return True
    secret = _totp_secret(org_id, user_id)
    if secret and verify_totp(secret, code):
        return True
    if verify_email_otp(user_id, code):
        return True
    if verify_sms_otp(user_id, code):
        return True
    if code and mfa_repo.consume_recovery_code(org_id, user_id, mfa_repo.hash_recovery_code(code)):
        return True
    return False


def assert_mfa_gate(
    *,
    org_id: str,
    user_id: str,
    attrs: dict | None,
    mfa_code: str | None,
    device_fingerprint: str | None = None,
    webauthn_assertion: dict | None = None,
) -> None:
    from app.core.config import settings

    if settings.app_env.lower() == "dev" and settings.iam_skip_mfa_in_dev:
        return
    if device_fingerprint and mfa_repo.is_device_trusted(org_id, user_id, device_fingerprint):
        return
    if not (attrs or {}).get("mfa_required"):
        enabled = mfa_repo.list_enabled_methods(org_id, user_id)
        policy = mfa_repo.get_org_security_policy(org_id) or {}
        required = policy.get("required_methods") or []
        if not required:
            return
        if not enabled:
            raise MfaRequired("MFA enrollment required for this organization")
    else:
        user = user_repo.get_by_id(org_id, user_id)
        enabled_legacy = user and user.get("mfa_enabled")
        enabled_methods = mfa_repo.list_enabled_methods(org_id, user_id)
        if not enabled_legacy and not enabled_methods:
            raise MfaRequired("MFA enrollment required for this role")
    if not mfa_code and not webauthn_assertion:
        raise MfaRequired("Valid MFA code required")
    if not verify_mfa_code(org_id, user_id, mfa_code or "", webauthn_assertion=webauthn_assertion):
        raise MfaRequired("Valid MFA code required")


def admin_reset_mfa(org_id: str, user_id: str) -> None:
    mfa_repo.disable_all_methods(org_id, user_id)
    mfa_repo.revoke_trusted_devices(org_id, user_id)
    from app.modules.core.iam.services.auth_audit_service import record_auth_event

    record_auth_event(event="mfa_admin_reset", success=True, org_id=org_id, user_id=user_id)
