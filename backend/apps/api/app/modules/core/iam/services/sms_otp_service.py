import secrets

from app.core.config import settings
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.services.redis_client import get_redis_client

_OTP_TTL_SECONDS = 600
_OTP_PREFIX = "iam:sms_otp"


def send_sms_otp(org_id: str, user_id: str, phone: str) -> None:
    if not settings.sms_api_url.strip():
        raise ValueError("SMS provider is not configured")
    code = f"{secrets.randbelow(1_000_000):06d}"
    client = get_redis_client()
    client.setex(f"{_OTP_PREFIX}:{user_id}", _OTP_TTL_SECONDS, code)
    mfa_repo.upsert_method(org_id, user_id, "sms_otp", enabled=True, metadata={"phone": phone})
    try:
        from app.modules.platform.notifications.providers.sms_provider import send_sms

        send_sms(phone, f"Your verification code is {code}")
    except Exception as exc:
        raise ValueError(f"Failed to send SMS OTP: {exc}") from exc


def verify_sms_otp(user_id: str, code: str) -> bool:
    client = get_redis_client()
    stored = client.get(f"{_OTP_PREFIX}:{user_id}")
    if not stored:
        return False
    if str(stored).strip() != str(code).strip():
        return False
    client.delete(f"{_OTP_PREFIX}:{user_id}")
    return True
