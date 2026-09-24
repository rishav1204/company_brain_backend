import base64
import io
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pyotp

from app.core.config import settings
from app.modules.core.iam.repositories import user_repo
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.modules.core.iam.services.email_otp_service import verify_email_otp
from app.modules.core.iam.services.sms_otp_service import verify_sms_otp
from app.modules.core.iam.services.secrets_crypto import decrypt_secret, encrypt_secret
from app.modules.core.iam.services.webauthn_service import finish_authentication

_MFA_CHALLENGE_TTL_SECONDS = 300
_MFA_CHALLENGE_TYP = "mfa_challenge"


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


def user_has_mfa_enabled(org_id: str, user_id: str) -> bool:
    """True when the user has completed MFA enrollment (TOTP or other methods)."""
    enabled = mfa_repo.list_enabled_methods(org_id, user_id)
    if enabled:
        return True
    user = user_repo.get_by_id(org_id, user_id)
    return bool(user and user.get("mfa_enabled"))


def issue_mfa_challenge_token(*, org_id: str, user_id: str, email: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _MFA_CHALLENGE_TYP,
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_MFA_CHALLENGE_TTL_SECONDS)).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def parse_mfa_challenge_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise MfaInvalid("Invalid or expired MFA challenge") from exc
    if payload.get("typ") != _MFA_CHALLENGE_TYP:
        raise MfaInvalid("Invalid MFA challenge")
    org_id = str(payload.get("org_id") or "")
    user_id = str(payload.get("user_id") or "")
    if not org_id or not user_id:
        raise MfaInvalid("Invalid MFA challenge")
    return {"org_id": org_id, "user_id": user_id, "email": payload.get("email")}


def qr_code_data_url(content: str) -> str | None:
    """PNG data URL for authenticator app scan (Microsoft Authenticator, Google, etc.)."""
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(content)
    buf = io.BytesIO()
    try:
        img.save(buf, format="PNG")
    except Exception:
        # Some qrcode builds need PIL; fall back silently.
        return None
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _totp_secret(org_id: str, user_id: str) -> str | None:
    row = mfa_repo.get_method(org_id, user_id, "totp")
    if row:
        meta = row.get("metadata") or {}
        secret = meta.get("secret")
        if secret:
            return decrypt_secret(str(secret))
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        return None
    with __import__("app.services.db", fromlist=["get_db_conn"]).get_db_conn() as conn:
        from app.services.db import set_rls_org

        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute("SELECT mfa_secret FROM core.users WHERE id = %s::uuid", (user_id,))
            legacy = cur.fetchone()
    return decrypt_secret(str((legacy or {}).get("mfa_secret") or "")) or None


def enroll_mfa(org_id: str, user_id: str) -> dict:
    secret = generate_totp_secret()
    encrypted = encrypt_secret(secret)
    mfa_repo.upsert_method(org_id, user_id, "totp", enabled=False, metadata={"secret": encrypted})
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        raise ValueError("User not found")
    uri = provisioning_uri(email=user["email"], secret=secret)
    return {
        "secret": secret,
        "provisioning_uri": uri,
        "qr_code_data_url": qr_code_data_url(uri),
        "issuer": "FinanceOS",
        "account_name": user["email"],
    }


def confirm_mfa_enrollment(org_id: str, user_id: str, code: str) -> list[str]:
    secret = _totp_secret(org_id, user_id)
    if not secret or not verify_totp(secret, code):
        raise MfaInvalid("Invalid MFA code")
    mfa_repo.upsert_method(org_id, user_id, "totp", enabled=True, metadata={"secret": encrypt_secret(secret)})
    with __import__("app.services.db", fromlist=["get_db_conn"]).get_db_conn() as conn:
        from app.services.db import set_rls_org

        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE core.users SET mfa_enabled = TRUE, mfa_secret = %s, updated_at = NOW() WHERE id = %s::uuid",
                (encrypt_secret(secret), user_id),
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
    attrs: dict | None = None,
    mfa_code: str | None = None,
    device_fingerprint: str | None = None,
    webauthn_assertion: dict | None = None,
    only_if_enrolled: bool = True,
) -> None:
    """Require a valid code only when the user already has MFA enabled.

    Enrollment is optional; password-only login is allowed when MFA is not enabled.
    """
    del attrs  # role attrs no longer force MFA at login; enrollment is explicit
    if device_fingerprint and mfa_repo.is_device_trusted(org_id, user_id, device_fingerprint):
        return
    if only_if_enrolled and not user_has_mfa_enabled(org_id, user_id):
        return
    if not mfa_code and not webauthn_assertion:
        raise MfaRequired("Valid MFA code required")
    if not verify_mfa_code(org_id, user_id, mfa_code or "", webauthn_assertion=webauthn_assertion):
        raise MfaInvalid("Invalid MFA code")


def admin_reset_mfa(org_id: str, user_id: str) -> None:
    mfa_repo.disable_all_methods(org_id, user_id)
    mfa_repo.revoke_trusted_devices(org_id, user_id)
    from app.modules.core.iam.services.auth_audit_service import record_auth_event

    record_auth_event(event="mfa_admin_reset", success=True, org_id=org_id, user_id=user_id)
