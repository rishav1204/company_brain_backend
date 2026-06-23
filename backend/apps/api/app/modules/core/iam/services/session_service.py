import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.modules.core.iam.repositories import session_repo


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def create_refresh_session(
    *,
    org_id: str,
    user_id: str,
    device_info: dict | None = None,
    ip_address: str | None = None,
    rotated_from: str | None = None,
) -> tuple[str, str]:
    raw_refresh = generate_refresh_token()
    refresh_hash = _hash_token(raw_refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.iam_refresh_token_ttl_seconds)
    session = session_repo.create_session(
        org_id=org_id,
        user_id=user_id,
        refresh_token_hash=refresh_hash,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address,
        rotated_from=rotated_from,
    )
    return raw_refresh, session["id"]


def resolve_refresh_session(raw_refresh: str) -> dict | None:
    session = session_repo.get_by_refresh_hash(_hash_token(raw_refresh))
    if not session or session.get("revoked"):
        return None
    expires_at = session.get("expires_at")
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    return session


def consume_refresh_session(raw_refresh: str) -> tuple[dict | None, bool]:
    """Atomically consume refresh token. Returns (session, reuse_detected)."""
    return session_repo.consume_refresh_session(_hash_token(raw_refresh))


def revoke_refresh_session(org_id: str, session_id: str) -> bool:
    return session_repo.revoke_session(org_id, session_id)
