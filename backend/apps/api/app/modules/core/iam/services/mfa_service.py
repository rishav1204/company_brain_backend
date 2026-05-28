import base64
import secrets

import pyotp

from app.modules.core.iam.repositories import user_repo
from app.services.db import get_db_conn, set_rls_org


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


def enroll_mfa(org_id: str, user_id: str) -> dict:
    secret = generate_totp_secret()
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE core.users
                SET mfa_secret = %s, mfa_enabled = FALSE, updated_at = NOW()
                WHERE id = %s::uuid AND org_id = %s::uuid
                RETURNING email
                """,
                (secret, user_id, org_id),
            )
            row = cur.fetchone()
    if not row:
        raise ValueError("User not found")
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri(email=row["email"], secret=secret),
    }


def confirm_mfa_enrollment(org_id: str, user_id: str, code: str) -> None:
    user = user_repo.get_by_id(org_id, user_id)
    if not user:
        raise ValueError("User not found")
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT mfa_secret FROM core.users WHERE id = %s::uuid",
                (user_id,),
            )
            row = cur.fetchone()
    secret = (row or {}).get("mfa_secret")
    if not secret or not verify_totp(secret, code):
        raise MfaInvalid("Invalid MFA code")
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE core.users SET mfa_enabled = TRUE, updated_at = NOW() WHERE id = %s::uuid",
                (user_id,),
            )


def assert_mfa_gate(*, org_id: str, user_id: str, attrs: dict | None, mfa_code: str | None) -> None:
    from app.core.config import settings

    if settings.app_env.lower() == "dev" and settings.iam_skip_mfa_in_dev:
        return
    if not (attrs or {}).get("mfa_required"):
        return
    user = user_repo.get_by_id(org_id, user_id)
    if not user or not user.get("mfa_enabled"):
        raise MfaRequired("MFA enrollment required for this role")
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute("SELECT mfa_secret FROM core.users WHERE id = %s::uuid", (user_id,))
            row = cur.fetchone()
    secret = (row or {}).get("mfa_secret")
    if not mfa_code or not verify_totp(secret or "", mfa_code):
        raise MfaRequired("Valid MFA code required")
