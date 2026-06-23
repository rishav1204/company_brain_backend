import redis

from app.core.config import settings

MAX_FAILURES = 10
LOCKOUT_SECONDS = 900


def _fail_key(email: str, ip: str | None) -> str:
    ip_part = ip or "unknown"
    return f"iam:lockout:{email.lower()}:{ip_part}"


def _locked_key(email: str, ip: str | None) -> str:
    return f"{_fail_key(email, ip)}:locked"


def is_locked(email: str, ip: str | None = None) -> bool:
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return bool(client.get(_locked_key(email, ip)))
    except Exception:
        return False


def record_failure(email: str, ip: str | None = None) -> int:
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        key = _fail_key(email, ip)
        count = client.incr(key)
        if count == 1:
            client.expire(key, LOCKOUT_SECONDS)
        if count >= MAX_FAILURES:
            client.setex(f"{key}:locked", LOCKOUT_SECONDS, "1")
        return int(count)
    except Exception:
        return 0


def clear_failures(email: str, ip: str | None = None) -> None:
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        key = _fail_key(email, ip)
        client.delete(key, f"{key}:locked")
    except Exception:
        pass
