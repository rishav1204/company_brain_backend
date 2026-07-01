from app.modules.core.iam.repositories import session_repo
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.services.cache.redis_cache import get_cached, set_cached


def _cached_org_security_policy(org_id: str) -> dict | None:
    cached = get_cached(org_id, "iam.org_security_policy")
    if cached is not None:
        return cached
    policy = mfa_repo.get_org_security_policy(org_id)
    set_cached(org_id, "iam.org_security_policy", policy or {}, ttl=60)
    return policy


def enforce_concurrent_session_limit(org_id: str, user_id: str) -> None:
    policy = _cached_org_security_policy(org_id)
    max_sessions = int((policy or {}).get("max_concurrent_sessions") or 10)
    active = session_repo.count_active_sessions(org_id, user_id)
    if active >= max_sessions:
        session_repo.revoke_oldest_sessions(org_id, user_id, keep=max_sessions - 1)
