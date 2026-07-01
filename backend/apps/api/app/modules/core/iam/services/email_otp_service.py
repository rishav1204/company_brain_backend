import secrets

from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.services.redis_client import get_redis_client

_OTP_TTL_SECONDS = 600
_OTP_PREFIX = "iam:email_otp"


def send_email_otp(org_id: str, user_id: str, email: str) -> None:
    code = f"{secrets.randbelow(1_000_000):06d}"
    client = get_redis_client()
    client.setex(f"{_OTP_PREFIX}:{user_id}", _OTP_TTL_SECONDS, code)
    mfa_repo.upsert_method(org_id, user_id, "email_otp", enabled=True, metadata={"email": email})
    try:
        from app.modules.platform.notifications.services.email_service import email_service

        email_service.send_email(
            to=email,
            subject="Your verification code",
            body=f"Your one-time verification code is: {code}\nValid for 10 minutes.",
        )
    except Exception:
        pass


def verify_email_otp(user_id: str, code: str) -> bool:
    client = get_redis_client()
    stored = client.get(f"{_OTP_PREFIX}:{user_id}")
    if not stored:
        return False
    if str(stored).strip() != str(code).strip():
        return False
    client.delete(f"{_OTP_PREFIX}:{user_id}")
    return True
